"""zkit_logic: pure logic for the zkit knob panels (no td import; unit-tested offline in test/test_zkit.py).

Clean-room, our own code. Spec: docs/research/BE_rudiment_zerror.md sections 5 + 6. Copied as text into a Text DAT
('zk_logic') inside every <comp>/controls, so a panel keeps working with the MCP gone.

Coordinates are panel pixels with the origin top-left, y down. Knob values u are 0-1 (normalised to the par's
normMin..normMax); presets store raw par values (like the original: raw, not normalised). Pure ASCII.
"""
import math
import random
import re

ARC = 270.0                      # degrees of knob sweep
A0 = -ARC / 2.0                  # start angle (7 o'clock), degrees clockwise from 12 o'clock
KINDS = ['knob', 'toggle', 'momentary', 'pulse', 'menu', 'swatch', 'string', 'slot', 'plus', 'group', 'rand',
         'theme', 'int']
KIND_ID = {'knob': 0, 'int': 0, 'toggle': 1, 'momentary': 2, 'pulse': 3, 'menu': 4, 'swatch': 5, 'string': 6,
           'slot': 7, 'plus': 8, 'group': 9, 'rand': 10, 'theme': 11}
# flag bits shared with the GLSL face shader
F_HOVER, F_ACTIVE, F_SELECT, F_OUT, F_LOCK, F_ON, F_MIDI, F_OPEN = 1, 2, 4, 8, 16, 32, 64, 128
MORPHABLE = ('knob', 'int', 'menu', 'toggle', 'swatchc')


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def norm(v, lo, hi):
    lo, hi = float(lo), float(hi)
    if hi == lo:
        return 0.0
    return clamp((float(v) - lo) / (hi - lo))


def norm_free(v, lo, hi):
    """Like norm but unclamped (to tell 'out of range')."""
    lo, hi = float(lo), float(hi)
    return 0.0 if hi == lo else (float(v) - lo) / (hi - lo)


def denorm(u, lo, hi):
    return float(lo) + clamp(float(u)) * (float(hi) - float(lo))


def value_to_angle(u):
    """0-1 -> degrees clockwise from 12 o'clock: 0 -> -135, 1 -> +135."""
    return A0 + ARC * clamp(float(u))


def angle_to_value(deg):
    return clamp((float(deg) - A0) / ARC)


def zero_u(lo, hi):
    """Where the 'zero' tick sits: at par value 0 when the range spans 0, else at the start."""
    lo, hi = float(lo), float(hi)
    if lo < 0.0 < hi:
        return norm(0.0, lo, hi)
    return 0.0


def drag_scale(shift=False, ctrl=False, alt=False):
    """Fine / coarse modifiers: Shift 1/10, Ctrl+Shift 1/50, Alt x4 (coarse)."""
    s = 1.0
    if shift and ctrl:
        s = 1.0 / 50.0
    elif shift:
        s = 1.0 / 10.0
    if alt:
        s *= 4.0
    return s


def drag_value(u0, dy_up, sens_px=200.0, shift=False, ctrl=False, alt=False):
    """u after dragging dy_up pixels upward (negative = down) from u0. sens_px of drag = the full range."""
    sens = max(1.0, float(sens_px))
    return clamp(float(u0) + float(dy_up) / sens * drag_scale(shift, ctrl, alt))


def steps_of(kind, lo, hi, n=0):
    """Number of discrete steps for int/menu/toggle (None = continuous)."""
    if kind == 'menu':
        return max(1, int(n) - 1)
    if kind == 'toggle':
        return 1
    if kind == 'int':
        return max(1, int(round(float(hi) - float(lo))))
    return None


def quantize_u(u, kind, lo, hi, n=0):
    st = steps_of(kind, lo, hi, n)
    if st is None:
        return clamp(u)
    return clamp(round(clamp(u) * st) / float(st))


def wheel_value(u, notches, kind, lo, hi, n=0, fine=False):
    """Scroll wheel: floats 1 % of range per notch (0.1 % fine); int/menu one step per notch."""
    st = steps_of(kind, lo, hi, n)
    if st is None:
        return clamp(u + float(notches) * (0.001 if fine else 0.01))
    return clamp(round(u * st + (1 if notches > 0 else -1) * max(1, abs(int(notches)))) / float(st))


def to_par(u, kind, lo, hi, n=0):
    """knob u -> value to write (menu = index, toggle = bool)."""
    u = clamp(float(u))
    if kind == 'toggle':
        return u >= 0.5
    if kind == 'menu':
        return 0 if n <= 1 else int(round(u * (int(n) - 1)))
    v = denorm(u, lo, hi)
    if kind == 'int':
        return int(round(v))
    return v


def from_par(v, kind, lo, hi, n=0):
    if kind == 'toggle':
        return 1.0 if v else 0.0
    if kind == 'menu':
        return 0.0 if n <= 1 else clamp(float(v) / (int(n) - 1))
    return norm(v, lo, hi)


def fmt_value(v, kind='knob', items=None):
    """Value text inside the knob: ~4 significant digits (0.322, 1.098, 19.70, 4030), ints plain, menus by name."""
    if kind == 'menu':
        items = items or []
        i = int(v)
        return str(items[i]) if 0 <= i < len(items) else str(i)
    if kind == 'toggle':
        return 'on' if v else 'off'
    if kind == 'int':
        return str(int(round(float(v))))
    v = float(v)
    if v == 0.0:
        return '0.000'
    a = abs(v)
    if a >= 10000:
        return '{:.0f}'.format(v)
    if a >= 1000:
        return '{:.0f}'.format(v)
    if a >= 100:
        return '{:.1f}'.format(v)
    if a >= 10:
        return '{:.2f}'.format(v)
    return '{:.3f}'.format(v)


def short_label(text, maxch):
    """Lower-case label cut to maxch characters (end cut, like the original)."""
    t = str(text).strip().lower()
    maxch = max(1, int(maxch))
    return t if len(t) <= maxch else t[:maxch]


# ---------------------------------------------------------------- layout
def metrics(d):
    """Pixel metrics for knob diameter d (all ints)."""
    d = int(d)
    return {
        'd': d,
        'cellw': int(round(d * 1.38)),
        'cellh': int(round(d * 1.56)),
        'top': int(round(d * 0.10)),          # knob top inside the cell
        'pad': int(round(d * 0.28)),          # panel padding
        'inset': int(round(d * 0.16)),        # group frame -> cells
        'head': int(round(d * 0.46)),         # group header height
        'ggap': int(round(d * 0.20)),         # gap between groups
        'bar': int(round(d * 1.20)),          # presets bar height (knob + label)
        'font': max(8, int(round(d * 0.205))),
        'tfont': max(8, int(round(d * 0.215))),
    }


def layout(groups, d=52, cols_max=12, collapsed=(), bar_items=None):
    """groups: [(group id, title, [(item id, span)])]; bar_items: [(item id, kind)] for the presets bar or None.
    Returns {'w','h','items': {id: (x, y, w, h)}, 'groups': {gid: (x, y, w, h, collapsed)}, 'bar': (x,y,w,h)|None,
    'cols'} with every knob cell on one shared column grid (frames line up)."""
    m = metrics(d)
    n_max = 1
    for _g, _t, items in groups:
        n_max = max(n_max, sum(int(s) for _i, s in items))
    cols = int(max(1, min(int(cols_max), 12, n_max)))
    inner_w = cols * m['cellw']
    frame_w = inner_w + 2 * m['inset']
    W = frame_w + 2 * m['pad']
    out = {'items': {}, 'groups': {}, 'bar': None, 'cols': cols, 'm': m}
    y = m['pad']
    if bar_items:
        bx = m['pad']
        out['bar'] = (bx, y, frame_w, m['bar'])
        # bar: plus, slots..., rand, amount, theme -- small cells, left to right
        sw = int(round(m['d'] * 0.86))
        x = bx
        for iid, kind in bar_items:
            w_ = sw if kind != 'gap' else int(sw * 0.4)
            if kind != 'gap':
                out['items'][iid] = (x, y, w_, m['bar'])
            x += w_
        W = max(W, x + m['pad'])
        y += m['bar'] + m['ggap']
    collapsed = set(collapsed)
    for gid, _title, items in groups:
        x0 = m['pad']
        gy = y
        if gid in collapsed:
            out['groups'][gid] = (x0, gy, frame_w, m['head'], True)
            y += m['head'] + m['ggap']
            continue
        col, row = 0, 0
        for iid, span in items:
            span = int(max(1, min(span, cols)))
            if col + span > cols:
                col, row = 0, row + 1
            out['items'][iid] = (x0 + m['inset'] + col * m['cellw'], gy + m['head'] + row * m['cellh'],
                                 span * m['cellw'], m['cellh'])
            col += span
        rows = row + 1 if items else 0
        gh = m['head'] + rows * m['cellh'] + m['inset']
        out['groups'][gid] = (x0, gy, frame_w, gh, False)
        y += gh + m['ggap']
    out['w'] = int(W)
    out['h'] = int(y - m['ggap'] + m['pad'])
    return out


def knob_circle(box, d, top):
    """(cx, cy, r) of the knob inside its cell box."""
    x, y, w, _h = box
    r = d / 2.0
    return (x + w / 2.0, y + top + r, r)


def hit(boxes, x, y):
    """First item id whose box holds (x, y); boxes = {id: (x, y, w, h)} or a list of (id, box). None if none."""
    it = boxes.items() if isinstance(boxes, dict) else boxes
    for iid, (bx, by, bw, bh) in it:
        if bx <= x < bx + bw and by <= y < by + bh:
            return iid
    return None


def is_click(dx, dy, tol=3.0):
    """A press+release that moved less than tol px is a click (select / type-in), not a drag."""
    return abs(dx) < tol and abs(dy) < tol


# ---------------------------------------------------------------- typed values
def parse_typed(text, kind='knob', items=None):
    """Typed text -> raw value, or None if it does not parse. Menus accept an index or an item name/prefix."""
    s = str(text).strip()
    if not s:
        return None
    if kind == 'menu':
        items = [str(i) for i in (items or [])]
        try:
            i = int(float(s))
            return i if 0 <= i < len(items) else None
        except ValueError:
            low = s.lower()
            for k, it in enumerate(items):
                if it.lower() == low:
                    return k
            for k, it in enumerate(items):
                if it.lower().startswith(low):
                    return k
            return None
    if kind == 'toggle':
        if s.lower() in ('1', 'on', 'true', 'yes'):
            return True
        if s.lower() in ('0', 'off', 'false', 'no'):
            return False
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return int(round(v)) if kind == 'int' else v


def type_key(buf, key, free=False):
    """Feed one key code into a type-in buffer. -> (buffer, action) with action None|'commit'|'cancel'.
    free = any printable ASCII (text / name fields: spaces, '#', '*', '@', '/'); else numbers + simple names."""
    k = int(key)
    if k in (13, 10, 3):
        return buf, 'commit'
    if k == 27:
        return buf, 'cancel'
    if k in (8, 127):
        return buf[:-1], None
    ch = chr(k) if 32 <= k < 127 else ''
    if ch and (free or ch.isalnum() or ch in '.-+e_'):
        return buf + ch, None
    return buf, None


# ---------------------------------------------------------------- presets / morph / randomise
def morph_one(a, b, t, kind):
    """One par between captured a and stored b at t (0-1). Floats lerp; ints round; menus/toggles/strings switch at
    t >= 0.5 (menus by index, given as numbers)."""
    t = clamp(float(t))
    if kind in ('knob', 'swatchc'):
        return lerp(float(a), float(b), t)
    if kind == 'int':
        return int(round(lerp(float(a), float(b), t)))
    if kind == 'toggle':
        return bool(b) if t >= 0.5 else bool(a)
    return b if t >= 0.5 else a


def morph_values(a, b, t, kinds):
    """a, b: {par: raw}; kinds: {par: kind}. Keys missing from b stay as in a; keys only in b come in from b."""
    out = dict(a)
    for k, vb in b.items():
        out[k] = morph_one(a.get(k, vb), vb, t, kinds.get(k, 'knob'))
    return out


def randomise(values, specs, amount, rng=None, locks=()):
    """values {par: raw}; specs {par: (kind, lo, hi, n)}; amount 0 = unchanged, 1 = anywhere in range.
    Floats/ints move toward a uniform random point; menus/toggles change with probability = amount.
    A random draw is made for every par in sorted order, so a lock never shifts the other pars' draws."""
    rng = rng or random.Random()
    a = clamp(float(amount))
    locks = set(locks)
    out = {}
    for k in sorted(values):
        v = values[k]
        r1, r2 = rng.random(), rng.random()
        if k in locks or k not in specs:
            out[k] = v
            continue
        kind, lo, hi, n = specs[k]
        if kind in ('knob', 'swatchc'):
            out[k] = lerp(float(v), denorm(r1, lo, hi), a)
        elif kind == 'int':
            out[k] = int(round(lerp(float(v), denorm(r1, lo, hi), a)))
        elif kind == 'menu':
            out[k] = int(r2 * max(1, int(n))) if r1 < a else v
        elif kind == 'toggle':
            out[k] = (not bool(v)) if r1 < a * 0.5 else bool(v)
        else:
            out[k] = v
    return out


def next_free_slot(stored, n_slots):
    """stored: set of slot numbers (1-based) holding a preset. -> first free slot, else None."""
    for s in range(1, int(n_slots) + 1):
        if s not in stored:
            return s
    return None


def brightness_scale(rgb, dy_up, sens_px=200.0):
    """Swatch drag: scale an RGB colour's brightness (keeps hue). Black lifts to grey."""
    r, g, b = [float(c) for c in rgb]
    mx = max(r, g, b)
    target = clamp(mx + float(dy_up) / max(1.0, float(sens_px)))
    if mx <= 1e-6:
        return (target, target, target)
    k = target / mx
    return (clamp(r * k), clamp(g * k), clamp(b * k))


# ================================================================ v2 (26 Oct, resumed after the crash): tokens, kinds,
# sized flow layout, properties menu, presets json, filter, popup placement. Spec BE section 6 + 7.0 corrections.
import json

# 7.0 #8: v5 knob colour palette (pink, orange-red, lime, cyan, blue, white); index 1 = default accent
PALETTE = [('pink', (0.92, 0.36, 0.60)), ('orange', (0.91, 0.27, 0.11)), ('lime', (0.62, 0.84, 0.24)),
           ('cyan', (0.25, 0.78, 0.84)), ('blue', (0.33, 0.53, 0.90)), ('white', (0.86, 0.86, 0.86))]
DEFAULT_COLOR = 1
SURFACE_BLUE = (0.357, 0.561, 0.816)     # 7.3: group/surface frame, title, dot (#5b8fd0)
SURFACE_DIM = (0.204, 0.314, 0.420)      # 7.3: empty slot outline (#34506b)
RED = (0.88, 0.25, 0.17)                 # out-of-range label, selection brackets, delete row

THEMES = {
    # 6.1 dark (default) and light; values are the sampled hex targets as 0-1 RGB
    'night': {'bg': (0.094, 0.098, 0.114), 'body': (0.176, 0.165, 0.173), 'track': (0.169, 0.169, 0.169),
              'label': (0.816, 0.816, 0.816), 'value': (0.741, 0.741, 0.741), 'row0': (0.106, 0.106, 0.106),
              'row1': (0.200, 0.188, 0.204), 'head': (0.0, 0.0, 0.0), 'plus': (0.12, 0.12, 0.13)},
    'day': {'bg': (0.769, 0.769, 0.769), 'body': (0.192, 0.188, 0.173), 'track': (0.62, 0.62, 0.62),
            'label': (0.133, 0.133, 0.133), 'value': (0.84, 0.84, 0.82), 'row0': (0.83, 0.83, 0.83),
            'row1': (0.75, 0.75, 0.76), 'head': (0.15, 0.15, 0.15), 'plus': (0.19, 0.19, 0.17)},
}

# render kinds shared with the GLSL face shader (field 'kind')
RK = {'knob': 0, 'int': 0, 'toggle': 1, 'momentary': 2, 'pulse': 3, 'menu': 4, 'swatch': 5, 'string': 6, 'slot': 7,
      'plus': 8, 'group': 9, 'rand': 10, 'theme': 11, 'row': 12, 'dot': 13, 'radio': 14, 'field': 15,
      'tcol': 16,   # tcol = colour of the text pixels inside its box (Text TOP spec rows carry no colour on 31550)
      'tab': 17, 'sbar': 18,   # page tab pill; scrollbar (a1 = thumb y, a2 = thumb h, view px)
      'drop': 19}              # dropdown field: pill + down triangle (a1 = 1 while its list is open)
# instance texture fields (one row each, one column per drawn instance)
FIELDS = ['x', 'y', 'w', 'h', 'cx', 'cy', 'r', 'u', 'kind', 'flags', 'cr', 'cg', 'cb', 'zu', 'a1', 'a2']


def kind_for_style(style, n_items=0):
    """TD par style -> kit kind (None = not shown)."""
    s = str(style)
    if s in ('Float', 'XY', 'XYZ', 'XYZW', 'WH', 'UV', 'UVW'):
        return 'knob'
    if s == 'Int':
        return 'int'
    if s == 'Toggle':
        return 'toggle'
    if s == 'Momentary':
        return 'momentary'
    if s == 'Pulse':
        return 'pulse'
    if s == 'Menu':
        return 'menu'
    if s == 'StrMenu':
        # a text field with suggestions (live menuSource or fixed items): drawn as a field + pop-up list whose items
        # are read at click time (28 Oct, dynamic menus), never a cycle knob with items frozen at panel build
        return 'dropdown'
    if s in ('RGB', 'RGBA'):
        return 'swatch'
    if s in ('Str', 'File', 'Folder', 'FileSave', 'Python', 'OP', 'COMP', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT',
             'POP', 'Object', 'PanelCOMP'):
        return 'string'
    return None


def ktype_choices(base):
    """7.0 #8 'knob type' row: a float/int knob can be shown as float / toggle / momentary."""
    if base in ('knob', 'int'):
        return [base, 'toggle', 'momentary']
    return [base]


def fmt4(v, kind='knob', items=None):
    """v5 value text (7.2): about 4 significant digits, toggles as 1.0000 / 0.0000, menus by item name."""
    if kind in ('toggle', 'momentary'):
        return '1.0000' if v else '0.0000'
    if kind in ('menu', 'int'):
        return fmt_value(v, kind, items)
    v = float(v)
    a = abs(v)
    if a >= 1000:
        return '{:.0f}'.format(v)
    if a >= 100:
        return '{:.1f}'.format(v)
    if a >= 10:
        return '{:.2f}'.format(v)
    if a >= 1:
        return '{:.3f}'.format(v)
    return '{:.4f}'.format(v)


def out_of_range(v, lo, hi):
    lo, hi = min(float(lo), float(hi)), max(float(lo), float(hi))
    return float(v) < lo - 1e-9 or float(v) > hi + 1e-9


def clamp_typed(v, lo, hi, cmin, cmax):
    """Typed raw values may leave the knob range unless clamp min / clamp max is on (label goes red, 6.2)."""
    v = float(v)
    if cmin:
        v = max(v, min(float(lo), float(hi)))
    if cmax:
        v = min(v, max(float(lo), float(hi)))
    return v


def menu_arc(idx, n):
    """Menu knob (7.0 #7): a short arc segment for item idx of n, the first one at 7 o'clock. -> (u0, u1)."""
    n = max(1, int(n))
    i = max(0, min(n - 1, int(idx)))
    return (i / float(n), (i + 1) / float(n))


def is_double(t_prev, id_prev, t, iid, window=0.35):
    return id_prev is not None and id_prev == iid and 0 <= float(t) - float(t_prev) <= window


def filter_step(cur, tgt, dt, tau):
    """Per-knob 'filter' (s): exponential approach; tau <= 0 = jump."""
    if tau <= 0:
        return float(tgt)
    k = 1.0 - math.exp(-max(0.0, float(dt)) / float(tau))
    return float(cur) + (float(tgt) - float(cur)) * k


def preset_dump(values):
    """{par: raw} -> json text (tuples become lists, bools stay bools)."""
    return json.dumps({k: (list(v) if isinstance(v, tuple) else v) for k, v in sorted(values.items())},
                      sort_keys=True, separators=(',', ':'))


def preset_load(text):
    try:
        d = json.loads(text) if text else {}
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def default_props():
    return {'recall': 1, 'sens': 1.0, 'min': None, 'max': None, 'filter': 0.0, 'clampmin': 0, 'clampmax': 0,
            'label': '', 'size': 1.0, 'color': DEFAULT_COLOR, 'showvalue': 1, 'ktype': '', 'default': None,
            'hidden': 0}


# 7.0 #8: properties list order (v4 and v5); tint names map to colours in the runtime
PROPS_ROWS = [
    ('ktype', 'knob type', None, 'cycle'), ('recall', 'recall', None, 'radio'), ('sens', 'sensitivity', None, 'num'),
    ('min', 'min', None, 'num'), ('max', 'max', None, 'num'), ('filter', 'filter', None, 'num'),
    ('clampmin', 'clamp min', None, 'radio'), ('clampmax', 'clamp max', None, 'radio'), ('label', 'label', None, 'text'),
    ('size', 'size', None, 'num'), ('color', 'color', None, 'dots'), ('showvalue', 'show value', None, 'radio'),
    ('chan', 'chan', None, 'info'),
    ('midi', 'MIDI', 'blue', 'info'), ('showop', 'show OP', 'teal', 'action'), ('savelayout', 'save to layout', 'green',
                                                                                  'layouts'),
    ('setdefault', 'set as default', 'bluegrey', 'action'), ('delete', 'delete', 'red', 'action'),
]
TINTS = {'blue': SURFACE_BLUE, 'teal': (0.27, 0.72, 0.68), 'green': (0.40, 0.78, 0.35), 'bluegrey': (0.55, 0.62, 0.72),
         'red': RED}
NUM_LIMITS = {'sens': (0.01, 100.0), 'size': (0.3, 6.0), 'filter': (0.0, 60.0)}


def menu_rows(kind):
    """Rows of the properties menu for an item kind (same order always; rows that do not apply are left out)."""
    rows = []
    for key, label, tint, rk in PROPS_ROWS:
        if kind in ('string', 'dropdown') and key in ('ktype', 'sens', 'min', 'max', 'filter', 'clampmin', 'clampmax'):
            continue
        if kind in ('toggle', 'momentary', 'pulse', 'menu', 'swatch') and key in ('min', 'max', 'clampmin', 'clampmax'):
            continue
        if kind in ('pulse',) and key in ('recall', 'filter', 'setdefault'):
            continue
        rows.append((key, label, tint, rk))
    return rows


def popup_rect(anchor, n_rows, row_h, w, pw, ph, gap=6):
    """Properties menu box beside the anchor cell (right side, else left), clamped inside the panel.
    -> (x, y, w, h); h = header + rows."""
    ax, ay, aw, ah = anchor
    h = (n_rows + 1) * row_h
    x = ax + aw + gap
    if x + w > pw:
        x = ax - gap - w
    x = max(0, min(int(x), int(pw - w)))
    y = max(0, min(int(ay), int(ph - h)))
    return (int(x), int(y), int(w), int(h))


# ---------------------------------------------------------------- dropdown pop-up list (28 Oct, dynamic menus)
DROP_MIN_W = 180


def drop_geom(anchor, n_items, row_h, want_w, pw, ph, top=0, gap=2):
    """Pop-up list of a dropdown field, in view px, kept inside the panel (pw x ph) and below the header (top), never
    over the field itself. One header row (the par name + 'type...') then the item rows. Below the field when the
    whole list fits there, else above when it fits there, else on the roomier side with as many rows as fit (the rest
    scroll, nvis rows). -> {'box', 'rh', 'nvis', 'n'}."""
    ax, ay, aw, ah = anchor
    n = max(1, int(n_items))                       # an empty list still shows one '(no items)' row
    rh = int(row_h)
    below = int((ph - gap - (ay + ah + gap)) // rh)        # rows (incl. the header row) that fit under the field
    above = int((ay - gap - top) // rh)                    # ... and over it, under the header
    if below >= n + 1 or (below >= above and below >= 2) or (above < 2 and below >= 2):
        nvis = max(1, min(n, below - 1))
        y = int(ay + ah + gap)
    elif above >= 2:
        nvis = max(1, min(n, above - 1))
        y = int(ay - gap - (nvis + 1) * rh)
    else:                                          # a tiny panel: as many rows as the whole view holds, pinned
        nvis = max(1, min(n, int((ph - top - 2 * gap) // rh) - 1))
        y = int(max(top, ph - (nvis + 1) * rh - gap))
    h = (nvis + 1) * rh
    w = int(min(max(1, pw - 2 * gap), max(int(aw), int(want_w), DROP_MIN_W)))
    x = int(max(gap, min(int(ax), int(pw - w - gap))))
    return {'box': (x, y, w, h), 'rh': rh, 'nvis': nvis, 'n': int(n_items)}


def fit_value(text, cell_w, font_px, measure, steps=(1.0, 0.85, 0.72)):
    """A VALUE (a name, a selection, an op path) in a field or a list row: case kept (labels are lowercased, values
    never), whole when a step of the font holds it; a path too long loses its leading folders ('../' + the tail,
    the op's own name whole); anything else is end-cut. -> (text, font_px)."""
    t = str(text).strip()
    fits = lambda s, f: measure(s, f) <= float(cell_w)
    for k in steps:
        if fits(t, float(font_px) * k):
            return t, float(font_px) * k
    f = float(font_px) * steps[-1]
    if '/' in t.strip('/'):
        parts = t.strip('/').split('/')
        while len(parts) > 1 and not fits('../' + '/'.join(parts), f):
            parts = parts[1:]
        tail = '../' + '/'.join(parts)
        if fits(tail, f) or len(parts) == 1:
            t = tail if fits(tail, f) else parts[0]
    while len(t) > 3 and not fits(t, f):
        t = t[:-1]
    return t, f


def drop_hit(g, x, y, off):
    """-> None (outside), 'head' or the absolute item index under (x, y); None on the '(no items)' row."""
    bx, by, bw, bh = g['box']
    if not (bx <= x < bx + bw and by <= y < by + bh):
        return None
    k = int((y - by) // g['rh'])
    if k <= 0:
        return 'head'
    i = int(off) + k - 1
    return i if 0 <= i < g['n'] else 'pad'


def drop_off(off, n, nvis):
    """First visible item, clamped."""
    return int(max(0, min(int(off), int(n) - int(nvis))))


def drop_start(cur_index, n, nvis):
    """Opening offset: the current item in view (centred when the list scrolls), else the top."""
    if cur_index is None or cur_index < nvis:
        return 0
    return drop_off(cur_index - nvis // 2, n, nvis)


def drop_thumb(g, off):
    """Scrollbar thumb of a long list: (x, y, w, h, thumb_y, thumb_h) in view px, or None when it all fits."""
    n, nvis = g['n'], g['nvis']
    if n <= nvis:
        return None
    bx, by, bw, bh = g['box']
    rh = g['rh']
    tw = max(3, int(rh * 0.25))
    tx, ty, th = bx + bw - tw - 2, by + rh + 2, nvis * rh - 4
    hh = max(8.0, th * nvis / float(n))
    yy = ty + (th - hh) * drop_off(off, n, nvis) / float(max(1, n - nvis))
    return (tx, ty, tw, th, yy, hh)


def _wrap_rows(widths, wrap_w):
    """Greedy wrap: number of rows the cell widths take at wrap width wrap_w (a cell wider than it gets a row)."""
    rows, cx = 0, 0
    for cw in widths:
        if rows == 0 or (cx > 0 and cx + cw > wrap_w):
            rows, cx = rows + 1, 0
        cx += cw
    return rows


def balanced_wrap(widths, inner_w):
    """Even rows (pages/scroll pass, 28 Oct): the smallest wrap width that keeps the greedy row count at inner_w, so
    9 cells on 8 columns go 5 + 4, not 8 + 1. Never more rows than the greedy wrap. -> wrap width px."""
    widths = [int(w) for w in widths]
    if not widths:
        return int(inner_w)
    n = _wrap_rows(widths, inner_w)
    if n <= 1:
        return int(inner_w)
    lo = max(max(widths), int(math.ceil(sum(widths) / float(n))))
    hi = int(inner_w)
    while lo < hi:                                             # rows(w) never grows with w: bisect the smallest w
        mid = (lo + hi) // 2
        if _wrap_rows(widths, mid) <= n:
            hi = mid
        else:
            lo = mid + 1
    return hi


def layout_flow(groups, d=56, cols_max=8, collapsed=(), bar_items=None, balance=False, inner_w_min=0, y_extra=0):
    """Sized flow layout. groups: [(gid, title, [(iid, size, wide)])] with size the continuous float multiplier
    (7.0 #5) and wide = cells across (strings 2). Cells wrap on a shared inner width of cols_max unit cells; a row is
    as tall as its tallest cell. Returns the same keys as layout() plus 'sizes' {iid: size}.
    balance = even rows per group (balanced_wrap); inner_w_min = keep at least this inner width (a page tab keeps the
    All width); y_extra = px left free between the presets bar and the first group (the tab row)."""
    m = metrics(d)
    units = 1.0
    for _g, _t, items in groups:
        units = max(units, sum(float(s) * float(wd) for _i, s, wd in items))
    cols = int(max(1, min(int(cols_max), math.ceil(units - 1e-9))))
    inner_w = cols * m['cellw']
    widest = max([int(round(m['cellw'] * float(s) * float(wd))) for _g, _t, it in groups for _i, s, wd in it] or [0])
    inner_w = max(inner_w, widest, int(inner_w_min))
    frame_w = inner_w + 2 * m['inset']
    W = frame_w + 2 * m['pad']
    out = {'items': {}, 'groups': {}, 'bar': None, 'cols': cols, 'm': m, 'sizes': {}}
    y = m['pad']
    if bar_items:
        sw = int(round(m['d'] * 0.86))
        x = m['pad']
        for iid, kind in bar_items:
            w_ = sw if kind != 'gap' else int(sw * 0.4)
            if kind != 'gap':
                out['items'][iid] = (x, y, w_, m['bar'])
            x += w_
        out['bar'] = (m['pad'], y, max(frame_w, x - m['pad']), m['bar'])
        W = max(W, x + m['pad'])
        y += m['bar'] + m['ggap']
    out['inner_w'] = inner_w
    out['y_extra_at'] = y
    y += int(y_extra)
    out['groups_y0'] = y
    collapsed = set(collapsed)
    for gid, _title, items in groups:
        x0 = m['pad']
        gy = y
        if gid in collapsed:
            out['groups'][gid] = (x0, gy, W - 2 * m['pad'], m['head'], True)
            y += m['head'] + m['ggap']
            continue
        wrap_w = inner_w
        if balance:
            wrap_w = balanced_wrap([int(round(m['cellw'] * float(s) * float(wd))) for _i, s, wd in items], inner_w)
        cx, ry, rowh = 0, gy + m['head'], 0
        for iid, s, wd in items:
            s = float(s)
            cw = int(round(m['cellw'] * s * float(wd)))
            ch = int(round(m['cellh'] * s))
            if cx > 0 and cx + cw > wrap_w:
                cx, ry, rowh = 0, ry + rowh, 0
            out['items'][iid] = (x0 + m['inset'] + cx, ry, cw, ch)
            out['sizes'][iid] = s
            cx += cw
            rowh = max(rowh, ch)
        gh = (ry + rowh) - gy + m['inset']
        out['groups'][gid] = (x0, gy, W - 2 * m['pad'], gh, False)
        y += gh + m['ggap']
    out['w'] = int(W)
    out['h'] = int(y - m['ggap'] + m['pad'])
    return out


def text_x(cx, text_w):
    """Left x that centres a text of width text_w on cx."""
    return float(cx) - float(text_w) / 2.0


def fit_label(text, cell_w, font_px, ratio=0.56):
    """Cut a label so it fits the cell (end cut, ~9 chars at 1x like the original)."""
    return short_label(text, max(3, int(float(cell_w) / max(1.0, float(font_px) * ratio))))


def fit_label_size(text, cell_w, font_px, ratio=0.56, steps=(1.0, 0.85, 0.72), measure=None):
    """Keep the whole label when it can (user rule: words stay intact): try the font at each step (few steps, so
    the Text TOP size buckets stay few) and cut only when even the smallest step cannot hold it.
    measure(text, font_px) -> width px (the panel's real text widths); without it, chars * font * ratio.
    -> (label, font_px)."""
    t = str(text).strip().lower()
    fits = (lambda s, f: measure(s, f) <= float(cell_w) * 0.88) if measure is not None else \
        (lambda s, f: len(s) <= int(float(cell_w) / max(1.0, f * ratio)))
    for k in steps:
        f = float(font_px) * k
        if fits(t, f):
            return t, f
    f = float(font_px) * steps[-1]
    if measure is None:
        return fit_label(t, cell_w, f, ratio), f
    if ' (' in t:                                              # a note in brackets goes first, whole
        t = t[:t.index(' (')].strip() or t
        for k in steps:
            if fits(t, float(font_px) * k):
                return t, float(font_px) * k
    words = t.split()
    while len(words) > 1 and (not fits(' '.join(words), f) or
                              ' '.join(words).count('(') > ' '.join(words).count(')')):
        words = words[:-1]                                     # drop whole trailing words, never cut one
    t = ' '.join(words)
    for k in steps:                                            # the shorter label at the largest size that fits
        if fits(t, float(font_px) * k):
            return t, float(font_px) * k
    while len(t) > 3 and not fits(t, f):                       # one word longer than the cell: end cut
        t = t[:-1]
    return t, f


def size_buckets(sizes, n_max=8, step=0.5):
    """Text TOP spec rows cannot carry their own font size (live 31550: fontsizex/fontsize columns ignored), so text
    is drawn by up to n_max Text TOPs, one per size. -> (bucket sizes sorted, {size: bucket index}); sizes are rounded
    to step px and, beyond n_max distinct sizes, snapped to the nearest kept one."""
    q = sorted(set(round(float(s) / step) * step for s in sizes))
    if len(q) > n_max:
        idx = [int(round(k * (len(q) - 1) / float(n_max - 1))) for k in range(n_max)]
        keep = [q[i] for i in sorted(set(idx))]
    else:
        keep = q
    m = {}
    for s in sizes:
        r = round(float(s) / step) * step
        m[s] = min(range(len(keep)), key=lambda i: abs(keep[i] - r))
    return keep, m


# ================================================================ v3 perf (26 Oct): tile culling, hit grid, diffs, hot
# text slots. docs/builds/zkit_perf.md. Pure ASCII, no td.
TILE = 64                        # face shader tile size, px: each pixel loops over its tile's instances only
CULL_PAD = 2.0                   # the shader rejects pixels more than 2 px outside an instance box


def grow_box(b, pad):
    return (b[0] - pad, b[1] - pad, b[2] + 2.0 * pad, b[3] + 2.0 * pad)


def union_box(a, b):
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def tile_grid(W, H, ts=TILE):
    """-> (tiles across, tiles down) for a W x H panel."""
    ts = max(1, int(ts))
    return max(1, (int(W) + ts - 1) // ts), max(1, (int(H) + ts - 1) // ts)


def tile_lists(boxes, W, H, ts=TILE, pad=CULL_PAD):
    """boxes: per instance (x, y, w, h) in panel px (y down), in draw order. -> list over tiles (row-major,
    tile = tx + ty * ntx) of the instance indices whose box grown by pad touches the tile, ascending (= draw order).
    Conservative: a pixel centre p in tile t can only be drawn by instances in lists[t]."""
    ntx, nty = tile_grid(W, H, ts)
    out = [[] for _ in range(ntx * nty)]
    for i, b in enumerate(boxes):
        x0, y0 = b[0] - pad, b[1] - pad
        x1, y1 = b[0] + b[2] + pad, b[1] + b[3] + pad
        if x1 < 0 or y1 < 0 or x0 >= ntx * ts or y0 >= nty * ts:
            continue
        tx0, tx1 = max(0, int(x0 // ts)), min(ntx - 1, int(x1 // ts))
        ty0, ty1 = max(0, int(y0 // ts)), min(nty - 1, int(y1 // ts))
        for ty in range(ty0, ty1 + 1):
            row = ty * ntx
            for tx in range(tx0, tx1 + 1):
                out[row + tx].append(i)
    return out


def tile_rows(lists):
    """Tile lists -> table rows for the tile texture: row 'count', then 'i0'..'iK-1' (K = longest list), one column
    per tile, unused entries 0. Texel (tile, 0) = count, (tile, 1 + k) = k-th instance index."""
    k_max = max([len(l) for l in lists] or [0])
    rows = [['count'] + [len(l) for l in lists]]
    for k in range(max(1, k_max)):
        rows.append(['i%d' % k] + [l[k] if k < len(l) else 0 for l in lists])
    return rows


def hit_grid(boxes, cell=TILE):
    """Hit-test grid: {(cx, cy): [ids in boxes' order]} for boxes = {id: (x, y, w, h)} (dict order kept)."""
    g = {}
    cell = float(cell)
    for iid, (bx, by, bw, bh) in boxes.items():
        for cy in range(int(by // cell), int((by + bh) // cell) + 1):
            for cx in range(int(bx // cell), int((bx + bw) // cell) + 1):
                g.setdefault((cx, cy), []).append(iid)
    return g


def hit_fast(grid, boxes, x, y, cell=TILE):
    """Same answer as hit(boxes, x, y) (first id in dict order whose box holds the point), via the grid."""
    for iid in grid.get((int(x // float(cell)), int(y // float(cell))), ()):
        bx, by, bw, bh = boxes[iid]
        if bx <= x < bx + bw and by <= y < by + bh:
            return iid
    return None


def diff_columns(prev, cur):
    """prev, cur: lists of equal-length tuples (one per table column). -> [(row, col, value)] of the cells that
    differ, or None when the shape changed (rewrite the table)."""
    if prev is None or len(prev) != len(cur) or (cur and len(prev[0]) != len(cur[0])):
        return None
    out = []
    for i, (a, b) in enumerate(zip(cur, prev)):
        if a != b:
            for k, (va, vb) in enumerate(zip(a, b)):
                if va != vb:
                    out.append((k, i, va))
    return out


def diff_rows(prev, cur):
    """prev, cur: lists of equal-length row tuples. -> [(row, col, value)] or None when the shape changed."""
    if prev is None or len(prev) != len(cur):
        return None
    out = []
    for r, (a, b) in enumerate(zip(cur, prev)):
        if a != b:
            if len(a) != len(b):
                return None
            for c, (va, vb) in enumerate(zip(a, b)):
                if va != vb:
                    out.append((r, c, va))
    return out


def hot_take(slots, stamps, iid, clock):
    """Hot text slots (a knob being dragged / a par moving every frame draws its value text in a small Text TOP of
    its own, so the big label buckets do not re-render). slots: list of ids or None, stamps: last use per slot.
    -> (slot index, changed) ; the least recently used slot is reused; slots never reorder (no needless rewrites)."""
    if iid in slots:
        k = slots.index(iid)
        stamps[k] = clock
        return k, False
    k = min(range(len(slots)), key=lambda j: (slots[j] is not None, stamps[j]))
    slots[k] = iid
    stamps[k] = clock
    return k, True


# ================================================================ v4 pages + scroll (28 Oct, T-231): the panel is a
# VIEWPORT, never sized to its content. A fixed header (presets bar + one tab per page + "All") stays on top, the
# groups scroll under it, a slim scrollbar sits in a right gutter. Every texture the kit makes is <= TEX_CAP a side.
# docs/builds/zkit.md "Pages + scroll". Coordinates: layouts are in CONTENT px (header at the top, groups below);
# view y = content y - scroll for the groups/knobs, header items do not scroll.
TEX_CAP = 4096                   # hard cap per texture side (Metal's limit is 16384 incl. the 2x Retina backing)
MAX_INST = TEX_CAP // 4          # the packed instance texture is 4 texels per instance in one row
SCREEN_MARGIN_H = 160            # menu bar + window title + dock, points
SCREEN_MARGIN_W = 80
FALLBACK_SCREEN = (1440, 900)    # when the screen size cannot be read
MIN_VIEW_H = 240
ALL_TAB = 'All'
MAIN_TAB = 'Main'
MAIN_FALLBACK = 12               # no essentials entry: Main = the first 12 controls of the first page


def viewport_cap(maxh=0, screen=None):
    """-> (cap_w, cap_h) in panel px. maxh > 0 = the user's Zkmaxh; 0 = fit the screen (screen = (w, h) points,
    None = FALLBACK_SCREEN), minus a margin. Both clamped to MIN_VIEW_H .. TEX_CAP."""
    sw, sh = screen if (screen and screen[0] and screen[1]) else FALLBACK_SCREEN
    cap_h = int(maxh) if maxh and int(maxh) > 0 else int(sh) - SCREEN_MARGIN_H
    cap_w = int(sw) - SCREEN_MARGIN_W
    return (max(MIN_VIEW_H, min(TEX_CAP, cap_w)), max(MIN_VIEW_H, min(TEX_CAP, cap_h)))


def gutter_w(d):
    return max(10, int(round(int(d) * 0.22)))


def cols_that_fit(d, cap_w):
    """Columns whose panel (pad + frame inset + cells + scrollbar gutter) fits cap_w."""
    m = metrics(d)
    room = int(cap_w) - 2 * m['pad'] - 2 * m['inset'] - gutter_w(d)
    return max(1, int(room // max(1, m['cellw'])))


def tab_metrics(d):
    m = metrics(d)
    return {'h': max(16, int(round(m['d'] * 0.40))), 'padx': max(6, int(round(m['d'] * 0.20))),
            'gap': max(3, int(round(m['d'] * 0.10))), 'font': m['font']}


def tab_boxes(names, x0, y0, width, d, measure=None):
    """Pills left to right, wrapping inside width. measure(text, font_px) -> px (else chars * font * 0.56).
    -> ({name: (x, y, w, h)}, total height)."""
    tm = tab_metrics(d)
    out, x, y = {}, x0, y0
    for nm in names:
        tw = measure(nm.lower(), tm['font']) if measure is not None else len(nm) * tm['font'] * 0.56
        w = int(math.ceil(tw)) + 2 * tm['padx']
        w = min(w, int(width))
        if x > x0 and x + w > x0 + width:
            x, y = x0, y + tm['h'] + tm['gap']
        out[nm] = (x, y, w, tm['h'])
        x += w + tm['gap']
    return out, (y - y0 + tm['h']) if names else 0


def layout_view(groups, d=56, cols_max=8, collapsed=(), bar_items=None, tab=None, cap=None, measure=None,
                balance=True, tabs=True, main=None):
    """The whole panel geometry for one tab. groups as layout_flow (gid '_g:<page>', title = page name).
    cap = (cap_w, cap_h) from viewport_cap. main = the Main group (gid '_g:Main', the COMP's essentials + macros) or
    None. Tabs: Main, one per page, All (All only when there are 2+ pages; none at all for one page and no Main).
    tab None = the default (Main if there is one, else All).
    -> lay (layout_flow keys, content coords, only the tab's groups, plus tab items '_t:<name>' in lay['items']) with
    lay['view'] = {W, H, hdr, smax, track, tab, tabs, overflow}; lay['all'] = the All layout (presets use it)."""
    cap_w, cap_h = cap or viewport_cap()
    m = metrics(d)
    cols_max = max(1, min(int(cols_max), cols_that_fit(d, cap_w)))
    titles = [t for _g, t, _i in groups]
    main = main if (main and main[2]) else None
    names = []
    if tabs and (main is not None or len(groups) > 1):
        names = ([MAIN_TAB] if main is not None else []) + titles + ([ALL_TAB] if len(groups) > 1 else [])
    show_tabs = bool(names)
    if tab not in names:
        tab = MAIN_TAB if main is not None and show_tabs else ALL_TAB
    if tab == ALL_TAB and ALL_TAB not in names and titles:
        tab = ALL_TAB                                            # one page: All is that page
    base = layout_flow(groups + ([main] if main is not None else []), d, cols_max, collapsed, bar_items,
                       balance=balance)
    tb, th = tab_boxes(names, m['pad'], base['y_extra_at'], base['w'] - 2 * m['pad'], d, measure)
    y_extra = th + m['ggap'] if show_tabs else 0
    lay_all = layout_flow(groups, d, cols_max, collapsed, bar_items, balance=balance, y_extra=y_extra) \
        if y_extra else base
    if main is not None:                                       # the All width must hold the Main rows too
        lay_all = layout_flow(groups, d, cols_max, collapsed, bar_items, balance=balance, y_extra=y_extra,
                              inner_w_min=base['inner_w'])
    if tab == ALL_TAB:
        lay = lay_all
    else:
        sel = [main] if tab == MAIN_TAB else [g for g in groups if g[1] == tab]
        lay = layout_flow(sel, d, lay_all['cols'], () if tab == MAIN_TAB else collapsed, bar_items,
                          balance=balance, inner_w_min=lay_all['inner_w'], y_extra=y_extra)
        lay['w'] = lay_all['w']
    tallest = lay_all['h']
    if main is not None:
        tallest = max(tallest, lay['h'] if tab == MAIN_TAB else
                      layout_flow([main], d, lay_all['cols'], (), bar_items, balance=balance,
                                  inner_w_min=lay_all['inner_w'], y_extra=y_extra)['h'])
    for nm, b in tb.items():
        lay['items']['_t:' + nm] = b
    hdr = int(lay_all['groups_y0'] - max(1, m['ggap'] // 2)) if (lay_all['groups'] or lay['groups']) else \
        int(lay_all['h'])
    overflow = tallest > cap_h
    gw = gutter_w(d) if overflow else 0
    H = int(min(cap_h, tallest))
    H = int(min(TEX_CAP, max(H, min(tallest, hdr + m['cellh'] + m['pad']))))
    W = int(min(TEX_CAP, lay_all['w'] + gw))
    smax = max(0, int(lay['h']) - H)
    track = None
    if overflow:
        sbw = max(4, int(round(gw * 0.45)))
        track = (W - gw + (gw - sbw) // 2, hdr + 4, sbw, max(8, H - hdr - 8))
    lay['view'] = {'W': W, 'H': H, 'hdr': hdr, 'smax': smax, 'track': track, 'tab': tab, 'tabs': names,
                   'overflow': overflow, 'gutter': gw}
    lay['all'] = lay_all
    return lay


def clamp_scroll(s, smax):
    return int(max(0, min(int(smax), int(round(float(s))))))


def thumb(view, scroll, content_h, min_h=20):
    """Scrollbar thumb (y, h) in view px, or None when nothing scrolls."""
    tr = view.get('track')
    if tr is None or view['smax'] <= 0:
        return None
    _x, ty, _w, th = tr
    vis = float(view['H'] - view['hdr'])
    tot = max(vis, float(content_h - view['hdr']))
    h = max(float(min(min_h, th)), th * vis / tot)
    y = ty + (th - h) * clamp_scroll(scroll, view['smax']) / float(view['smax'])
    return (y, h)


def thumb_drag(view, s0, dy, content_h):
    """Scroll after dragging the thumb dy px (down = +), from scroll s0."""
    t = thumb(view, s0, content_h)
    if t is None:
        return 0
    room = max(1.0, view['track'][3] - t[1])
    return clamp_scroll(s0 + dy * view['smax'] / room, view['smax'])


def wheel_scroll(scroll, notch, view, step):
    """Wheel up (notch > 0) shows what is above: scroll goes down by step px per notch."""
    return clamp_scroll(scroll - float(notch) * float(step), view['smax'])


F_SCROLL = 256                   # instance flag: content (moved by the scroll uniform, clipped under the header)


def stage_window(view, scroll, content_h, n_in=None, budget=None, per=4):
    """The content band kept in the tables while scrolling ('stage'): the viewport plus a margin of half a view
    above and below, so a wheel notch inside it changes one uniform only. n_in(lo, hi) -> knobs in that band (to
    stay under the instance budget, ~per instances each). -> (o, wy0, wy1): stage y = content y - o (the header
    keeps its view y above hdr), the band is content y wy0 .. wy1. No overflow: (0, 0, content_h)."""
    if not view.get('overflow'):
        return (0, 0, int(content_h))
    hdr, H = view['hdr'], view['H']
    s = clamp_scroll(scroll, view['smax'])
    lo, hi = s + hdr, s + H
    m = max(0, min((H - hdr) // 2, (TEX_CAP - H) // 2))
    while m > 0 and n_in is not None and budget is not None and per * n_in(lo - m, hi + m) > budget:
        m //= 2
    wy0 = max(hdr, lo - m)
    wy1 = min(max(int(content_h), hi), hi + m)
    return (wy0 - hdr, wy0, wy1)


def in_window(win, view, scroll):
    """Is the viewport at this scroll still inside the stage band?"""
    if not view.get('overflow'):
        return True
    s = clamp_scroll(scroll, view['smax'])
    return win[1] <= s + view['hdr'] and s + view['H'] <= win[2]


def where(view, x, y, scroll):
    """Panel px (view) -> ('sbar' | 'head' | 'content', x, y in content px). The gutter at the right is the
    scrollbar's; header items keep their y, content y = view y + scroll."""
    tr = view.get('track')
    if tr is not None and x >= view['W'] - view['gutter'] and y >= view['hdr']:
        return ('sbar', x, y)
    if y < view['hdr']:
        return ('head', x, y)
    return ('content', x, y + clamp_scroll(scroll, view['smax']))


def visible(boxes, ids, view, scroll):
    """ids (in order) whose content box shows in the view at this scroll (between the header and the bottom)."""
    s = clamp_scroll(scroll, view['smax'])
    lo, hi = view['hdr'], view['H']
    out = []
    for i in ids:
        b = boxes.get(i)
        if b is not None and b[1] - s + b[3] > lo and b[1] - s < hi:
            out.append(i)
    return out


def scroll_cfg_load(text):
    """zk_cfg 'scroll' = 'All:120,Look:0' -> {tab: px}."""
    out = {}
    for part in str(text or '').split(','):
        if ':' in part:
            k, v = part.rsplit(':', 1)
            try:
                out[k] = int(float(v))
            except ValueError:
                pass
    return out


def scroll_cfg_dump(d):
    return ','.join('%s:%d' % (k, int(v)) for k, v in sorted(d.items()) if ',' not in k and ':' not in k)



# ================================================================ v4b essentials, macros, hidden pages (28 Oct; user:
# "skim down while keeping and adding functionality"). builders/zk_essentials.json:
# {"<COMP name>": {"main": [par names in order], "macros": [{"name": "Zkm1", "label": "Energy",
#                  "drives": [{"par": "Speed", "from": 0.2, "to": 3.0}, ...]}]}}
NUMERIC_STYLES = ('Float', 'Int', 'XY', 'XYZ', 'XYZW', 'WH', 'UV', 'UVW', 'RGB', 'RGBA', 'Toggle', 'Menu')


def validate_essentials(entry, par_style):
    """entry = the COMP's essentials dict (or None); par_style(name) -> TD style of an existing par / tuplet, None if
    unknown. -> (main names, macros [{name, label, drives}], notes [str]). Unknown names are skipped with a note; a
    macro with no valid drive is dropped; macro names must be Zk-prefixed custom par names (Zkm1..)."""
    notes = []
    if not isinstance(entry, dict):
        return [], [], notes
    main = []
    for n in entry.get('main') or []:
        if not isinstance(n, str) or par_style(n) is None:
            notes.append('main: no par %s' % n)
        elif n not in main:
            main.append(n)
    macros = []
    for k, mc in enumerate(entry.get('macros') or []):
        if not isinstance(mc, dict):
            continue
        name = str(mc.get('name') or 'Zkm%d' % (k + 1))
        name = name[:1].upper() + name[1:].lower()
        if not name.startswith('Zkm') or not name.isalnum():
            notes.append('macro %s: name must be Zkm<n>' % name)
            continue
        drives = []
        for d in mc.get('drives') or []:
            try:
                par, f, t = str(d['par']), float(d['from']), float(d['to'])
            except (KeyError, TypeError, ValueError):
                notes.append('macro %s: bad drive %r' % (name, d))
                continue
            st = par_style(par)
            if st is None:
                notes.append('macro %s: no par %s' % (name, par))
            elif st not in NUMERIC_STYLES:
                notes.append('macro %s: %s is %s, not numeric' % (name, par, st))
            else:
                drives.append({'par': par, 'from': f, 'to': t})
        if drives:
            mo = {'name': name, 'label': str(mc.get('label') or name), 'drives': drives}
            try:
                mo['default'] = clamp(float(mc['default']))
            except (KeyError, TypeError, ValueError):
                pass
            macros.append(mo)
        else:
            notes.append('macro %s: no valid drive, skipped' % name)
    return main, macros, notes


def macro_value(u, drive, style='Float'):
    """Driven par value at macro u (0-1): linear from -> to; ints / menus round, toggles switch at the middle."""
    v = float(drive['from']) + (float(drive['to']) - float(drive['from'])) * clamp(float(u))
    if style == 'Toggle':
        return v >= 0.5
    if style in ('Int', 'Menu'):
        return int(round(v))
    return v


def macro_init(cur, drive):
    """Starting macro value for a new macro par: where its first driven par sits now (0 if outside / flat)."""
    f, t = float(drive['from']), float(drive['to'])
    if t == f:
        return 0.0
    return clamp((float(cur) - f) / (t - f))


def resolve_main(names, items):
    """names: par / tuplet names in display order; items: [(iid, pars, tuplet)] in panel order. -> item ids in the
    names' order (a tuplet name brings all its items, e.g. Offset -> Offset1, Offset2)."""
    out = []
    for n in names:
        for iid, pars, tup in items:
            if (iid == n or n in pars or tup == n) and iid not in out:
                out.append(iid)
    return out


def main_fallback(groups, n=MAIN_FALLBACK):
    """No essentials entry: the first n controls of the first page. groups: [(page, ids)]."""
    return list(groups[0][1][:n]) if groups else []


def is_page_switch(style, name):
    """A page's FIRST par that switches the page's feature on (Vhon, Geoon, Lineson, Soundon): a toggle named
    '...on'. While it is off, the page shows only that toggle (the rest is unused; nothing is lost)."""
    n = str(name).lower()
    return str(style) == 'Toggle' and len(n) > 3 and n.endswith('on') and not n.endswith('ion')


def uid_par_ok(name, expected, current):
    """PX module pars are uid-named (M4progress = uid 4's progress) and the essentials assume PX's DEFAULT_STACK
    (expected {uid: type}). Such a par is shown / driven only while that uid still holds the expected type
    (current {uid: type} from px_stack). Pars that are not M<uid>... always pass."""
    m = re.match(r'^M(\d+)[a-z]', str(name))
    if m is None or not expected:
        return True
    uid = int(m.group(1))
    return uid in expected and current.get(uid) == expected[uid]


def stack_types(rows):
    """px_stack rows -> {uid: type}."""
    out = {}
    for r in rows:
        try:
            out[int(float(r['uid']))] = str(r['type'])
        except (KeyError, ValueError, TypeError):
            pass
    return out


def stack_inactive(rows):
    """PX_pointfx px_stack rows [{uid, type, enabled}] -> page names ('M<uid>_<type>') of disabled modules."""
    out = set()
    for r in rows:
        try:
            if int(float(r.get('enabled', 1))) == 0:
                out.add('M%d_%s' % (int(float(r['uid'])), r['type']))
        except (KeyError, ValueError, TypeError):
            pass
    return out


# ================================================================ debug panel skin (style_debug_panel in zkit.py, 26 Oct)
# The jazib-td debug panel (/project1/debug, td/debug.py) predates the kit. Its T-72/T-73 cost model stays: the text
# view is 4 Text TOPs over one background, recomposited only when a spec table changes (~2 Hz, only while the window
# is open). The skin changes colours, swaps the flat background for a static band image (cooks once) and draws the fps
# graph in a GLSL TOP that only cooks when fps_hist changes and only while the window shows it.
DEBUG_THEMES = {
    'night': {'bg': THEMES['night']['bg'], 'band_head': (0.0, 0.0, 0.0), 'band_title': (0.150, 0.146, 0.158),
              'zebra': (0.118, 0.120, 0.137), 'bar': SURFACE_BLUE, 'accent': PALETTE[DEFAULT_COLOR][1],
              'text': {'head': (0.95, 0.95, 0.95), 'title': (0.48, 0.68, 0.93), 'body': THEMES['night']['label'],
                       'err': (1.0, 0.45, 0.36)},
              'graph_bg': (0.071, 0.074, 0.086), 'grid': (0.20, 0.21, 0.24), 'warn': RED},
    'day': {'bg': THEMES['day']['bg'], 'band_head': THEMES['day']['head'], 'band_title': THEMES['day']['row1'],
            'zebra': (0.735, 0.735, 0.742), 'bar': (0.20, 0.36, 0.62), 'accent': PALETTE[DEFAULT_COLOR][1],
            'text': {'head': (0.95, 0.95, 0.95), 'title': (0.13, 0.27, 0.52), 'body': THEMES['day']['label'],
                     'err': (0.70, 0.10, 0.06)},
            'graph_bg': (0.83, 0.83, 0.83), 'grid': (0.66, 0.66, 0.67), 'warn': (0.75, 0.12, 0.06)},
}
BAND = {'none': 0, 'head': 1, 'title': 2, 'zebra': 3}


def debug_bands(kinds):
    """kinds: the debug view's fixed line slots (view_lines kinds: head / title / body / err / '').
    -> one BAND code per line: head lines, section titles, and inside a section every second row (counted from its
    title) zebra; the blank line that closes a section stays plain."""
    out, sec = [], None
    for i, k in enumerate(kinds):
        nxt = kinds[i + 1] if i + 1 < len(kinds) else None
        if k == 'head':
            out.append(BAND['head'])
            sec = None
        elif k == 'title':
            out.append(BAND['title'])
            sec = i
        elif sec is not None and not (k == '' and nxt == 'title'):
            out.append(BAND['zebra'] if (i - sec) % 2 == 0 else BAND['none'])
        else:
            out.append(BAND['none'])
    return out


def _v3(c):
    return 'vec3(%.4f, %.4f, %.4f)' % tuple(float(x) for x in c)


def debug_bg_glsl(bands, theme='night', h=520, pad_top=6, line_h=15):
    """Static background shader for the debug text view (no inputs, no time: cooks once). Line i covers
    y (from the bottom) h - pad_top - (i+1)*line_h .. h - pad_top - i*line_h (= debug_panel_rt.line_at)."""
    t = DEBUG_THEMES[theme]
    arr = ', '.join(str(int(b)) for b in bands) or '0'
    n = max(1, len(bands))
    return '''// zkit skin: debug panel background (bands per line slot). Generated by zkit_logic.debug_bg_glsl.
out vec4 fragColor;
const int N = %d;
const int B[N] = int[N](%s);
void main() {
    vec2 p = gl_FragCoord.xy;
    vec3 col = %s;
    float yt = %.1f - %.1f - p.y;
    int i = int(floor(yt / %.1f));
    if (yt >= 0.0 && i >= 0 && i < N) {
        int b = B[i];
        if (b == 1) col = %s;
        else if (b == 2) { col = %s; if (p.x < 3.0) col = %s; }
        else if (b == 3) col = %s;
        bool lastHead = (b == 1) && (i + 1 >= N || B[i + 1] != 1);
        float yb = %.1f - %.1f - float(i + 1) * %.1f;
        if (lastHead && p.y - yb < 2.0) col = %s;
    }
    fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
''' % (n, arr, _v3(t['bg']), float(h), float(pad_top), float(line_h), _v3(t['band_head']), _v3(t['band_title']),
       _v3(t['bar']), _v3(t['zebra']), float(h), float(pad_top), float(line_h), _v3(t['accent']))


def debug_graph_glsl(theme='night', rate=60.0, top_frac=1.15):
    """fps graph shader: fps history arrives as a texture buffer uniform `uFps` (GLSL TOP Arrays page: fps_chop as a
    texture buffer, no CHOP to TOP), N = its sample count. Night bg, grid at the target rate and half of it, area +
    1.5 px line in the kit accent, red where a bucket is below 90 % of target. Indices clamped (T-35)."""
    t = DEBUG_THEMES[theme]
    return '''// zkit skin: debug panel fps graph. Generated by zkit_logic.debug_graph_glsl.
uniform samplerBuffer uFps;
out vec4 fragColor;
const float RATE = %.3f;
const float TOPV = %.3f;
float val(float u) {
    int n = textureSize(uFps);
    if (n < 1) return 0.0;
    float f = clamp(u, 0.0, 1.0) * float(n - 1);
    int i0 = clamp(int(floor(f)), 0, n - 1);
    int i1 = min(i0 + 1, n - 1);
    return mix(texelFetch(uFps, i0).r, texelFetch(uFps, i1).r, fract(f));
}
void main() {
    vec2 res = uTDOutputInfo.res.zw;
    vec2 p = gl_FragCoord.xy;
    vec3 col = %s;
    float yr = p.y / res.y * TOPV;
    float py = 1.0 / res.y * TOPV;
    if (abs(yr - RATE) < py * 0.6 || abs(yr - RATE * 0.5) < py * 0.6) col = %s;
    float du = 1.0 / res.x;
    float u = p.x / max(1.0, res.x - 1.0);
    float v = val(u);
    vec3 acc = (v < RATE * 0.9) ? %s : %s;
    if (yr < v) col = mix(col, acc, 0.04 + 0.16 * smoothstep(0.55, 1.0, yr / max(v, 1e-3)));
    float s = (val(u + du) - val(u - du)) * 0.5 / py;
    float d = abs(yr - v) / py / sqrt(1.0 + s * s);
    col = mix(col, acc, clamp(1.6 - d, 0.0, 1.0));
    fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
''' % (float(rate), float(rate) * top_frac, _v3(t['graph_bg']), _v3(t['grid']), _v3(t['warn']), _v3(t['accent']))


# ---- drop-in (28 Oct, user: "i can add it to different scenes and still have it work"): a panel names its COMP and
# the window names its panel by RELATIVE paths, so a loaded / copied COMP drives itself, never the original.
def target_rel(panel_path, comp_path):
    """zk_cfg 'target' for a panel at panel_path inside comp_path: '..' per level ('controls' -> '..',
    'controls/params' -> '../..'). The panel resolves it with panel.op(value)."""
    if not panel_path.startswith(comp_path.rstrip('/') + '/'):
        return comp_path                                  # a panel outside its COMP: absolute (rare)
    depth = len(panel_path[len(comp_path.rstrip('/')) + 1:].split('/'))
    return '/'.join(['..'] * depth)


def winop_rel(win_path, op_path):
    """controls_window 'winop' for an op inside the window's parent: its path below that parent (a bare name
    resolves as a sibling of the window, T-244)."""
    base = win_path.rsplit('/', 1)[0]
    return op_path[len(base) + 1:] if op_path.startswith(base + '/') else op_path


def is_abs(v):
    return str(v or '').startswith('/')

