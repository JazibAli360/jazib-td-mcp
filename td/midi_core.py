"""midi_core: pure MIDI mapping engine for jazib-td (own, clean-room implementation).

Stdlib only, ASCII only, no TD imports: copied into a Text DAT inside TD and imported by tests.
Features from docs/research/AR_tdmap_midi.md sections 1, 2, 4, 6 (no TDXMap code was read).

Value spaces:
- control space: what the controller sends, normalised 0..1 (raw/127, raw14/16383).
- norm (par space): position of the parameter inside [min, max], 0..1. norm = apply_curve(control)
  (after invert). Feedback and takeover go back with invert_curve.
"""
import json
import math

VERSION = 1
KINDS = ('cc', 'cc14', 'note', 'pitchbend', 'aftertouch', 'program')
MODES = ('absolute', 'relative_2c', 'relative_bin', 'relative_sign', 'toggle', 'momentary', 'trigger')
RELATIVE_MODES = ('relative_2c', 'relative_bin', 'relative_sign')
BUTTON_MODES = ('toggle', 'momentary', 'trigger')
TAKEOVERS = ('none', 'pickup', 'scale')
CURVES = ('linear', 'ease_in', 'ease_out', 'ease_in_out', 'log', 'exp', 'smoothstep')  # + 'steps:N'

FIELDS = ['id', 'bank', 'label', 'kind', 'channel', 'number', 'target', 'par', 'min', 'max', 'default',
          'curve', 'invert', 'mode', 'takeover', 'smooth', 'clamp', 'feedback', 'step']
DEFAULTS = {
    'id': '', 'bank': 0, 'label': '', 'kind': 'cc', 'channel': 0, 'number': 0, 'target': '', 'par': '',
    'min': 0.0, 'max': 1.0, 'default': None, 'curve': 'linear', 'invert': False, 'mode': 'absolute',
    'takeover': 'none', 'smooth': 0.0, 'clamp': True, 'feedback': False, 'step': 1.0 / 127.0,
}
_TYPES = {'id': str, 'bank': int, 'label': str, 'kind': str, 'channel': int, 'number': int, 'target': str,
          'par': str, 'min': float, 'max': float, 'default': float, 'curve': str, 'invert': bool,
          'mode': str, 'takeover': str, 'smooth': float, 'clamp': bool, 'feedback': bool, 'step': float}


def _clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def _to_bool(v):
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'yes', 'on', 't', 'y')
    return bool(v)


# ---------------------------------------------------------------- mappings

def new_mapping(**kw):
    """Full mapping dict with defaults; unknown keys raise KeyError. Values are coerced to field types."""
    m = dict(DEFAULTS)
    for k, v in kw.items():
        if k not in DEFAULTS:
            raise KeyError('unknown mapping field: %s' % k)
        m[k] = v
    for k, t in _TYPES.items():
        v = m[k]
        if v is None and k == 'default':
            continue
        try:
            m[k] = _to_bool(v) if t is bool else t(v)
        except (TypeError, ValueError):
            pass  # left as is; validate() reports it
    return m


def _curve_ok(c):
    if c in CURVES:
        return True
    if isinstance(c, str) and c.startswith('steps:'):
        try:
            return int(c[6:]) >= 2
        except ValueError:
            return False
    return False


def validate(m):
    """List of error strings (empty = valid). Empty target/par is allowed (unbound slot)."""
    errs = []
    for k in m:
        if k not in DEFAULTS:
            errs.append('unknown field: %s' % k)
    for k, t in _TYPES.items():
        if k not in m:
            errs.append('missing field: %s' % k)
            continue
        v = m[k]
        if k == 'default' and v is None:
            continue
        if t is float:
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        elif t is int:
            ok = isinstance(v, int) and not isinstance(v, bool)
        else:
            ok = isinstance(v, t)
        if not ok:
            errs.append('%s: expected %s, got %r' % (k, t.__name__, v))
    if errs:
        return errs
    if not m['id']:
        errs.append('id: empty')
    if m['bank'] < 0:
        errs.append('bank: must be >= 0')
    if m['kind'] not in KINDS:
        errs.append('kind: %r not in %s' % (m['kind'], KINDS))
    if not 0 <= m['channel'] <= 16:
        errs.append('channel: must be 0 (any) or 1..16')
    lo, hi = {'cc14': (0, 31), 'aftertouch': (-1, 127)}.get(m['kind'], (0, 127))
    if not lo <= m['number'] <= hi:
        errs.append('number: must be %d..%d for %s' % (lo, hi, m['kind']))
    if m['min'] == m['max']:
        errs.append('min == max')
    if not _curve_ok(m['curve']):
        errs.append('curve: %r invalid' % m['curve'])
    if m['mode'] not in MODES:
        errs.append('mode: %r not in %s' % (m['mode'], MODES))
    elif m['mode'] in RELATIVE_MODES and m['kind'] != 'cc':
        errs.append('mode: relative modes need kind cc')
    if m['takeover'] not in TAKEOVERS:
        errs.append('takeover: %r not in %s' % (m['takeover'], TAKEOVERS))
    if m['smooth'] < 0:
        errs.append('smooth: must be >= 0')
    if m['step'] <= 0:
        errs.append('step: must be > 0')
    return errs


def mapping_matches_bank(m, active_bank):
    return m['bank'] == 0 or m['bank'] == active_bank


def select_bank(mappings, active_bank):
    """Mappings live in this bank (bank 0 = always)."""
    return [m for m in mappings if mapping_matches_bank(m, active_bank)]


def banks_in(mappings):
    return sorted({m['bank'] for m in mappings if m['bank'] != 0})


def next_id(mappings, prefix='m'):
    used = {m['id'] for m in mappings}
    i = 1
    while '%s%d' % (prefix, i) in used:
        i += 1
    return '%s%d' % (prefix, i)


def retarget(mappings, old_prefix, new_prefix):
    """Rewrite target paths after a COMP was renamed/moved. Returns the number changed."""
    n = 0
    for m in mappings:
        t = m['target']
        if t == old_prefix or t.startswith(old_prefix.rstrip('/') + '/'):
            m['target'] = new_prefix + t[len(old_prefix):]
            n += 1
    return n


# ---------------------------------------------------------------- events

def parse_event(kind, channel, number, value, value2=None):
    """Normalise one MIDI message to an event dict.

    kind: cc | cc14 | note | noteon | noteoff | pitchbend | aftertouch | program.
    cc14: value = 14-bit 0..16383, or value = MSB and value2 = LSB.
    pitchbend: value = 14-bit 0..16383 (8192 centre), or value = LSB and value2 = MSB (wire order);
      a negative value is read as signed -8192..8191. number is forced to 0.
    aftertouch: number = note for poly pressure, -1 (or None) for channel pressure.
    program: number = program number, value ignored (value = number/127).
    Returns {kind, channel, number, value (0..1), raw (int)} and 'on' (bool) for note.
    """
    kind = str(kind).lower()
    channel = int(channel)
    number = -1 if number is None else int(number)
    if kind in ('noteon', 'noteoff', 'note'):
        raw = 0 if kind == 'noteoff' else int(value)
        return {'kind': 'note', 'channel': channel, 'number': number, 'value': _clamp01(raw / 127.0),
                'raw': raw, 'on': raw > 0}
    if kind == 'cc14':
        raw = int(value) * 128 + int(value2) if value2 is not None else int(value)
        return {'kind': 'cc14', 'channel': channel, 'number': number, 'value': _clamp01(raw / 16383.0), 'raw': raw}
    if kind == 'pitchbend':
        if value2 is not None:
            raw = int(value2) * 128 + int(value)
        else:
            raw = int(value)
            if raw < 0:
                raw += 8192
        return {'kind': 'pitchbend', 'channel': channel, 'number': 0, 'value': _clamp01(raw / 16383.0), 'raw': raw}
    if kind == 'program':
        return {'kind': 'program', 'channel': channel, 'number': number, 'value': _clamp01(number / 127.0),
                'raw': number}
    if kind in ('cc', 'aftertouch'):
        raw = int(value)
        return {'kind': kind, 'channel': channel, 'number': number, 'value': _clamp01(raw / 127.0), 'raw': raw}
    raise ValueError('unknown event kind: %r' % kind)


def _norm_key(s):
    return ''.join(ch for ch in str(s).lower() if ch.isalnum())


_ROW_KINDS = [  # (substring of normalised message text, kind) - first hit wins
    ('noteoff', 'noteoff'), ('noteon', 'noteon'), ('note', 'note'), ('polyaftertouch', 'aftertouch'),
    ('polypressure', 'aftertouch'), ('aftertouch', 'aftertouch'), ('pressure', 'aftertouch'),
    ('pitch', 'pitchbend'), ('bend', 'pitchbend'), ('program', 'program'), ('control', 'cc'), ('cc', 'cc'),
]


def parse_midiin_row(row):
    """Adapt one MIDI In DAT row (dict of column -> str) to an event, or None (sysex, clock, unknown).

    ASSUMED columns (TD MIDI In DAT, to be confirmed live on 2025.31550 by lane B): 'message' (or 'type')
    holding text like 'Control Change' / 'Note On' / 'Note Off' / 'Pitch Bend' / 'Program Change' /
    'Channel Pressure' / 'Poly Aftertouch'; 'channel' 1..16; 'index' (controller / note number; also
    accepted: 'number', 'controller', 'note'); 'value' (also 'velocity'). Column names and message
    texts are matched case/space/underscore-insensitive. A pitch bend 'value' above 127 or below 0 is
    read as 14-bit (signed if negative); an optional 'value2' column is used as the MSB.
    """
    r = {_norm_key(k): ('' if v is None else str(v).strip()) for k, v in row.items()}

    def pick(*names):
        for n in names:
            if r.get(n, '') != '':
                return r[n]
        return None

    msg = _norm_key(pick('message', 'type', 'msg', 'event') or '')
    kind = None
    for sub, k in _ROW_KINDS:
        if sub in msg:
            kind = k
            break
    if kind is None:
        return None

    def num(s, default=0):
        try:
            return int(round(float(s)))
        except (TypeError, ValueError):
            return default

    ch = num(pick('channel', 'chan', 'ch'), 1)
    number = num(pick('index', 'number', 'controller', 'note', 'ctrl', 'num'), 0)
    value = num(pick('value', 'velocity', 'val'), 0)
    v2 = pick('value2', 'msb')
    if kind == 'pitchbend':
        if v2 is not None:
            return parse_event('pitchbend', ch, 0, value, num(v2))
        return parse_event('pitchbend', ch, 0, value if (value > 127 or value < 0) else value * 128)
    if kind == 'aftertouch' and 'channel' in msg and 'poly' not in msg:
        number = -1
    if kind == 'program':
        number = num(pick('index', 'number', 'program', 'value'), 0)
    return parse_event(kind, ch, number, value)


class Cc14Joiner:
    """Joins 14-bit CC pairs (MSB = CC n 0..31, LSB = CC n+32), per channel + number, no timeouts.

    MSB then LSB (spec order): MSB is held, the LSB emits. A later LSB alone (fine-only change) emits
    with the held MSB. LSB first: the LSB is held and the next MSB emits; the order is then remembered.
    numbers: optional iterable of MSB numbers to join (others pass through as None from wants()).
    """

    def __init__(self, numbers=None):
        self.numbers = None if numbers is None else set(int(n) for n in numbers)
        self._s = {}

    def wants(self, number):
        n = number if number < 32 else number - 32
        if not 0 <= number < 64:
            return False
        return self.numbers is None or n in self.numbers

    def _state(self, key):
        return self._s.setdefault(key, {'msb': None, 'lsb': 0, 'msb_pending': False, 'lsb_pending': False,
                                        'order': None})

    def feed(self, channel, number, value):
        """Feed one CC. Returns (msb_number, value14) when a joined value is ready, else None."""
        if not self.wants(number):
            return None
        value = int(value) & 127
        if number < 32:
            s = self._state((channel, number))
            if s['lsb_pending']:
                s.update(msb=value, lsb_pending=False, order='lsb_first')
                return (number, value * 128 + s['lsb'])
            s.update(msb=value, msb_pending=True)
            return None
        n = number - 32
        s = self._state((channel, n))
        s['lsb'] = value
        if s['msb_pending']:
            s.update(msb_pending=False, order='msb_first')
            return (n, s['msb'] * 128 + value)
        if s['order'] == 'msb_first' and s['msb'] is not None:
            return (n, s['msb'] * 128 + value)
        s['lsb_pending'] = True
        return None

    def feed_event(self, event):
        """Feed a parsed cc event; returns a cc14 event dict or None."""
        out = self.feed(event['channel'], event['number'], event['raw'])
        if out is None:
            return None
        return parse_event('cc14', event['channel'], out[0], out[1])

    def reset(self):
        self._s.clear()


def matches(m, event, active_bank):
    """True when this mapping takes this event: bank, kind, channel (0 = any) and number.
    pitchbend and program ignore number; aftertouch number -1 = channel pressure."""
    if not mapping_matches_bank(m, active_bank):
        return False
    if m['kind'] != event['kind']:
        return False
    if m['channel'] != 0 and m['channel'] != event['channel']:
        return False
    if m['kind'] in ('pitchbend', 'program'):
        return True
    return m['number'] == event['number']


# ---------------------------------------------------------------- curves

_LOGK = 9.0  # log: log10(1 + 9x); exp is its inverse


def _steps(curve):
    return int(curve[6:]) if isinstance(curve, str) and curve.startswith('steps:') else 0


def apply_curve(x, curve):
    """Map control 0..1 to par norm 0..1. All curves are monotonic, 0->0 and 1->1."""
    x = _clamp01(x)
    if curve == 'linear':
        return x
    if curve == 'ease_in':
        return x * x
    if curve == 'ease_out':
        return 1.0 - (1.0 - x) ** 2
    if curve == 'ease_in_out':
        return 4.0 * x ** 3 if x < 0.5 else 1.0 - (2.0 - 2.0 * x) ** 3 / 2.0
    if curve == 'smoothstep':
        return x * x * (3.0 - 2.0 * x)
    if curve == 'log':
        return math.log10(1.0 + _LOGK * x)
    if curve == 'exp':
        return (10.0 ** x - 1.0) / _LOGK
    n = _steps(curve)
    if n >= 2:
        return round(x * (n - 1)) / (n - 1)
    raise ValueError('unknown curve: %r' % curve)


def invert_curve(y, curve):
    """Inverse of apply_curve (steps:N returns the step level itself)."""
    y = _clamp01(y)
    if curve == 'linear':
        return y
    if curve == 'ease_in':
        return math.sqrt(y)
    if curve == 'ease_out':
        return 1.0 - math.sqrt(1.0 - y)
    if curve == 'ease_in_out':
        return (y / 4.0) ** (1.0 / 3.0) if y < 0.5 else 1.0 - (2.0 * (1.0 - y)) ** (1.0 / 3.0) / 2.0
    if curve == 'smoothstep':
        return _clamp01(0.5 - math.sin(math.asin(_clamp(1.0 - 2.0 * y, -1.0, 1.0)) / 3.0))
    if curve == 'log':
        return (10.0 ** y - 1.0) / _LOGK
    if curve == 'exp':
        return math.log10(1.0 + _LOGK * y)
    n = _steps(curve)
    if n >= 2:
        return round(y * (n - 1)) / (n - 1)
    raise ValueError('unknown curve: %r' % curve)


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


# ---------------------------------------------------------------- value stepping

def relative_delta(raw, mode):
    """Signed ticks from one relative-encoder CC value.
    relative_2c: 1..63 = +n, 65..127 = n-128 (127 = -1). relative_bin: raw - 64 (65 = +1, 63 = -1).
    relative_sign: bit 6 = sign, 1 = +1, 65 = -1."""
    raw = int(raw) & 127
    if mode == 'relative_2c':
        return raw - 128 if raw >= 64 else raw
    if mode == 'relative_bin':
        return raw - 64
    if mode == 'relative_sign':
        return -(raw & 63) if raw & 64 else raw & 63
    raise ValueError('not a relative mode: %r' % mode)


def _press(event):
    return event.get('on', event['value'] > 0) if event['kind'] == 'note' else event['value'] > 0


def step_value(m, event, current_norm, state=None, quantum=0.0):
    """New par norm (0..1) for this event, or None = no change.

    absolute: control (inverted if invert) -> curve. relative: ticks * step added in control space.
    With state (a dict, one per runtime), relative steps accumulate in state['rel'][id] so small steps
    still add up on Int/Menu pars; the accumulator resyncs to current_norm when the par moved by more
    than quantum (par resolution in norm units, e.g. 1/(max-min) for Int) from what it produced.
    toggle: press flips (current >= 0.5 -> 0, else 1; invert ignored); momentary: press 1, release 0; trigger: press 1.
    Buttons ignore curve; invert swaps 0/1.
    """
    mode = m['mode']
    if mode in BUTTON_MODES:
        on = _press(event)
        hi, lo = (0.0, 1.0) if m['invert'] else (1.0, 0.0)
        if mode == 'toggle':
            if not on:
                return None
            return 0.0 if current_norm >= 0.5 else 1.0
        if mode == 'momentary':
            return hi if on else lo
        return hi if on else None
    if mode in RELATIVE_MODES:
        d = relative_delta(event['raw'], mode) * m['step']
        if m['invert']:
            d = -d
        pos = None
        acc = None
        if state is not None:
            acc = state.setdefault('rel', {})
            pos = acc.get(m['id'])
            if pos is not None and abs(apply_curve(pos, m['curve']) - current_norm) > quantum + 1e-9:
                pos = None
        if pos is None:
            pos = invert_curve(current_norm, m['curve'])
        pos = _clamp01(pos + d)
        if acc is not None:
            acc[m['id']] = pos
        return apply_curve(pos, m['curve'])
    x = event['value']
    if m['invert']:
        x = 1.0 - x
    return apply_curve(x, m['curve'])


class TakeoverState:
    """Per-mapping soft-takeover memory: picked flag + last incoming norm."""

    def __init__(self):
        self.rows = {}

    def get(self, mid):
        return self.rows.setdefault(mid, {'picked': False, 'last_in': None})

    def reset(self, mid=None):
        if mid is None:
            self.rows.clear()
        else:
            self.rows.pop(mid, None)

    def picked(self, mid):
        return self.rows.get(mid, {}).get('picked', False)


def takeover_reset(state, mapping_id=None):
    """Forget pickup state (call when the par changed from elsewhere, on bank switch or preset load).
    mapping_id None = all."""
    state.reset(mapping_id)


def takeover_gate(m, state, incoming_norm, current_norm, tol=0.02):
    """(allow, out_norm). Only absolute mode is gated; other modes pass.
    pickup: ignore until the control meets current (|in - cur| <= tol) or crosses it between two moves.
    scale: from the first move, map the remaining travel so control and par meet at the end of travel,
    then follow 1:1 once they are within tol."""
    if m['takeover'] == 'none' or m['mode'] != 'absolute':
        return True, incoming_norm
    s = state.get(m['id'])
    if s['picked']:
        s['last_in'] = incoming_norm
        return True, incoming_norm
    last = s['last_in']
    s['last_in'] = incoming_norm
    if abs(incoming_norm - current_norm) <= tol:
        s['picked'] = True
        return True, incoming_norm
    if m['takeover'] == 'pickup':
        if last is not None and (last - current_norm) * (incoming_norm - current_norm) <= 0:
            s['picked'] = True
            return True, incoming_norm
        return False, current_norm
    if last is None or incoming_norm == last:
        return False, current_norm
    if incoming_norm > last:
        span = 1.0 - last
        out = current_norm + (incoming_norm - last) * (1.0 - current_norm) / span if span > 0 else 1.0
    else:
        out = current_norm - (last - incoming_norm) * current_norm / last if last > 0 else 0.0
    out = _clamp01(out)
    if abs(out - incoming_norm) <= tol:
        s['picked'] = True
    return True, out


# ---------------------------------------------------------------- par values

def _menu_index(norm, menu_count):
    return int(_clamp(round(norm * (menu_count - 1)), 0, menu_count - 1))


def to_par_value(m, norm, style, menu_count=None):
    """Value to write for a par of this style. Float(-likes): min + norm*(max-min), clamped to the
    range when clamp. Int: rounded int. Toggle/Momentary/Pulse: bool (norm >= 0.5; Pulse True = pulse
    it). Menu/StrMenu: int menuIndex (0..menu_count-1 when menu_count, else round(min..max))."""
    if m['clamp']:
        norm = _clamp01(norm)
    if style in ('Toggle', 'Momentary', 'Pulse'):
        return norm >= 0.5
    if style in ('Menu', 'StrMenu') and menu_count:
        return _menu_index(norm, int(menu_count))
    v = m['min'] + norm * (m['max'] - m['min'])
    if m['clamp']:
        v = _clamp(v, min(m['min'], m['max']), max(m['min'], m['max']))
    if style in ('Int', 'Menu', 'StrMenu'):
        return int(round(v))
    return float(v)


def from_par_value(m, value, style, menu_count=None):
    """Par value -> norm 0..1 (for feedback and takeover)."""
    if style in ('Toggle', 'Momentary', 'Pulse'):
        return 1.0 if _to_bool(value) else 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if style in ('Menu', 'StrMenu') and menu_count:
        return _clamp01(v / (int(menu_count) - 1)) if int(menu_count) > 1 else 0.0
    span = m['max'] - m['min']
    if span == 0:
        return 0.0
    return _clamp01((v - m['min']) / span)


def smooth(prev, target, dt, seconds):
    """Exponential smoothing: reaches ~63% of the way after `seconds`. seconds <= 0 = no smoothing."""
    if prev is None or seconds <= 0 or dt <= 0:
        return target if prev is None or seconds <= 0 else prev
    a = 1.0 - math.exp(-dt / seconds)
    return prev + (target - prev) * a


class Smoother:
    """Per-mapping smoothing targets; step() once per frame for every id with a target."""

    def __init__(self, eps=1e-4):
        self.eps = eps
        self.values = {}
        self.targets = {}

    def set_target(self, mid, target, current=None):
        if mid not in self.values:
            self.values[mid] = target if current is None else current
        self.targets[mid] = target

    def step(self, mid, dt, seconds):
        v = smooth(self.values.get(mid), self.targets[mid], dt, seconds)
        if abs(v - self.targets[mid]) <= self.eps:
            v = self.targets[mid]
            self.targets.pop(mid)
        self.values[mid] = v
        return v

    def active(self):
        return list(self.targets)

    def reset(self, mid=None):
        for d in (self.values, self.targets):
            d.clear() if mid is None else d.pop(mid, None)


def feedback_messages(m, norm):
    """MIDI to send so LEDs / motor faders show norm: list of (kind, channel, number, value_int).
    cc -> one cc 0..127; cc14 -> MSB cc n then LSB cc n+32; note -> velocity 127/0; pitchbend ->
    14-bit value; aftertouch -> 0..127; program -> []. Channel 0 (any) sends on channel 1."""
    if not m['feedback'] or m['kind'] == 'program':
        return []
    ch = m['channel'] or 1
    if m['mode'] in BUTTON_MODES:
        c = 1.0 if norm >= 0.5 else 0.0
        if m['invert']:
            c = 1.0 - c
    else:
        c = invert_curve(norm, m['curve'])
        if m['invert']:
            c = 1.0 - c
    k = m['kind']
    if k == 'cc14':
        v = int(round(c * 16383))
        return [('cc', ch, m['number'], v >> 7), ('cc', ch, m['number'] + 32, v & 127)]
    if k == 'pitchbend':
        return [('pitchbend', ch, 0, int(round(c * 16383)))]
    if k == 'note':
        return [('note', ch, m['number'], 127 if c >= 0.5 else 0)]
    return [(k, ch, m['number'], int(round(c * 127)))]


# ---------------------------------------------------------------- smart learn

def classify_learn(events):
    """Decide what was moved from a short burst of parsed events.
    Returns {'kind','mode','channel','number','control'} (control: absolute | encoder | button | 14bit |
    pitchbend), or None for no events. Buttons get mode 'toggle' (runtime may pick momentary/trigger
    from the par style). Relative: needs no 0 value and repeats or <= 2 distinct values; values near 64
    -> relative_bin, 1..15/113..127 -> relative_2c, 1..15/65..79 -> relative_sign; 65..71 alone is read
    as relative_bin (ambiguous with sign -1)."""
    if not events:
        return None
    pb = [e for e in events if e['kind'] == 'pitchbend']
    if pb:
        return {'kind': 'pitchbend', 'mode': 'absolute', 'channel': pb[0]['channel'], 'number': 0,
                'control': 'pitchbend'}
    notes = [e for e in events if e['kind'] == 'note']
    if notes:
        return {'kind': 'note', 'mode': 'toggle', 'channel': notes[0]['channel'], 'number': notes[0]['number'],
                'control': 'button'}
    for e in events:
        if e['kind'] == 'cc14':
            return {'kind': 'cc14', 'mode': 'absolute', 'channel': e['channel'], 'number': e['number'],
                    'control': '14bit'}
    ccs = [e for e in events if e['kind'] == 'cc']
    if not ccs:
        e = events[0]
        return {'kind': e['kind'], 'mode': 'absolute', 'channel': e['channel'], 'number': e['number'],
                'control': 'absolute'}
    nums = {}
    for e in ccs:
        nums.setdefault((e['channel'], e['number']), []).append(e['raw'])
    for (ch, n) in nums:
        if n < 32 and (ch, n + 32) in nums:
            return {'kind': 'cc14', 'mode': 'absolute', 'channel': ch, 'number': n, 'control': '14bit'}
    (ch, n), vals = max(nums.items(), key=lambda kv: len(kv[1]))
    out = {'kind': 'cc', 'mode': 'absolute', 'channel': ch, 'number': n, 'control': 'absolute'}
    distinct = set(vals)
    if distinct <= {0, 127}:
        out.update(mode='toggle', control='button')
        return out
    repeats = len(vals) - len(distinct)
    if 0 not in distinct and (repeats >= 1 or len(distinct) <= 2):
        if all(57 <= v <= 71 and v != 64 for v in vals):
            out.update(mode='relative_bin', control='encoder')
        elif all(1 <= v <= 15 or 113 <= v <= 127 for v in vals):
            out.update(mode='relative_2c', control='encoder')
        elif all(1 <= v <= 15 or 65 <= v <= 79 for v in vals):
            out.update(mode='relative_sign', control='encoder')
    return out


# ---------------------------------------------------------------- table / JSON I/O

def _cell(k, v):
    if v is None:
        return ''
    if _TYPES[k] is bool:
        return '1' if v else '0'
    if _TYPES[k] is float:
        return repr(float(v))
    return str(v)


def to_rows(mappings):
    """[FIELDS] + one row of strings per mapping (Table DAT ready)."""
    return [list(FIELDS)] + [[_cell(k, m.get(k, DEFAULTS[k])) for k in FIELDS] for m in mappings]


def from_rows(rows):
    """Inverse of to_rows. Column order comes from the header row; missing columns get defaults,
    unknown columns are ignored, blank rows skipped."""
    if not rows:
        return []
    head = [str(h).strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not any(str(c).strip() for c in r):
            continue
        kw = {}
        for i, h in enumerate(head):
            if h not in DEFAULTS or i >= len(r):
                continue
            s = str(r[i]).strip()
            t = _TYPES[h]
            if s == '' and t is not str:
                kw[h] = None if h == 'default' else DEFAULTS[h]
            elif t is bool:
                kw[h] = _to_bool(s)
            elif t is int:
                kw[h] = int(float(s))
            elif t is float:
                kw[h] = float(s)
            else:
                kw[h] = s
        out.append(new_mapping(**kw))
    return out


def to_json(mappings, active_bank=1, presets=None, indent=1):
    cfg = {'version': VERSION, 'active_bank': int(active_bank),
           'mappings': [{k: m.get(k, DEFAULTS[k]) for k in FIELDS} for m in mappings]}
    if presets is not None:
        cfg['presets'] = presets
    return json.dumps(cfg, indent=indent, sort_keys=False)


def from_json(text):
    """-> {version, active_bank, mappings (full dicts), presets}. Accepts a bare list of mappings too."""
    data = json.loads(text)
    if isinstance(data, list):
        data = {'mappings': data}
    ver = int(data.get('version', VERSION))
    if ver > VERSION:
        raise ValueError('config version %d is newer than %d' % (ver, VERSION))
    maps = [new_mapping(**{k: v for k, v in m.items() if k in DEFAULTS}) for m in data.get('mappings', [])]
    return {'version': ver, 'active_bank': int(data.get('active_bank', 1)), 'mappings': maps,
            'presets': data.get('presets', {})}


# ---------------------------------------------------------------- controller templates

CONTROLLER_PRESETS = {
    'generic_8x8': {
        'description': 'ASSUMPTION, not a real device: 8 faders CC 0-7 and 8 knobs CC 16-23, channel 1, '
                       'absolute. A common default layout; check your controller and re-learn.',
        'source': '',
        'verified': False,
        'controls': [{'label': 'fader %d' % (i + 1), 'kind': 'cc', 'channel': 1, 'number': i, 'mode': 'absolute'}
                     for i in range(8)] +
                    [{'label': 'knob %d' % (i + 1), 'kind': 'cc', 'channel': 1, 'number': 16 + i, 'mode': 'absolute'}
                     for i in range(8)],
    },
}


def mappings_from_preset(name, bank=1, prefix=None, existing=()):
    """Unbound mapping slots (empty target/par) from a controller template."""
    p = CONTROLLER_PRESETS[name]
    out = []
    pool = list(existing)
    for c in p['controls']:
        m = new_mapping(id=next_id(pool, prefix or name + '_'), bank=bank, label=c['label'], kind=c['kind'],
                        channel=c['channel'], number=c['number'], mode=c['mode'])
        pool.append(m)
        out.append(m)
    return out
