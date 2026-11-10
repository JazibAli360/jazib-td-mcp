"""zctl_logic: pure logic for the zctl control surface COMP (no td import; unit-tested offline).

Clean-room design: docs/research/BE_rudiment_zerror.md. Knob values are always 0-1 (normalised); targets are mapped
with the bind's lo/hi and kind (float, int, toggle, menu). Presets are JSON {knob name: value}.
Pure ASCII (copied into a Text DAT inside the COMP).
"""
import json
import math
import random
import re

BIND_COLS = ['id', 'knob', 'label', 'path', 'par', 'lo', 'hi', 'kind', 'menun', 'lock', 'src']
PRESET_COLS = ['id', 'name', 'values']
CURVES = ['linear', 'ease', 'smooth']
KINDS = ['float', 'int', 'toggle', 'menu']


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def normalize(v, lo, hi):
    lo, hi = float(lo), float(hi)
    if hi == lo:
        return 0.0
    return clamp((float(v) - lo) / (hi - lo))


def denormalize(u, lo, hi):
    return float(lo) + clamp(float(u)) * (float(hi) - float(lo))


def curve(t, name='linear'):
    """Shape 0-1 progress. linear; ease = cosine in-out; smooth = smootherstep (zero 1st+2nd derivative at ends)."""
    t = clamp(float(t))
    name = str(name).lower()
    if name == 'ease':
        return 0.5 - 0.5 * math.cos(math.pi * t)
    if name == 'smooth':
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    return t


def lerp(a, b, t):
    return a + (b - a) * t


def morph(a, b, t, curve_name='linear'):
    """Blend two {key: value} dicts at progress t; keys only in b come in from b, keys only in a stay."""
    k = curve(t, curve_name)
    out = dict(a)
    for key, vb in b.items():
        out[key] = lerp(float(a.get(key, vb)), float(vb), k)
    return out


def to_target(u, lo, hi, kind='float', menun=0):
    """Knob 0-1 -> the value to write on the target parameter."""
    u = clamp(float(u))
    if kind == 'toggle':
        return u >= 0.5
    if kind == 'menu':
        n = int(menun)
        return 0 if n <= 1 else int(round(u * (n - 1)))
    v = denormalize(u, lo, hi)
    if kind == 'int':
        return int(round(v))
    return v


def from_target(v, lo, hi, kind='float', menun=0):
    """Target parameter value -> knob 0-1 (menu: v is the menu index)."""
    if kind == 'toggle':
        return 1.0 if v else 0.0
    if kind == 'menu':
        n = int(menun)
        return 0.0 if n <= 1 else clamp(float(v) / (n - 1))
    return normalize(v, lo, hi)


def randomize(values, amount, rng=None, locks=None):
    """amount 0 = unchanged, 1 = uniform over the full 0-1 range; in between = pulled toward a random point."""
    rng = rng or random.Random()
    locks = locks or {}
    a = clamp(float(amount))
    out = {}
    for k in sorted(values):
        v = float(values[k])
        r = rng.random()  # drawn for every knob so a lock never shifts the others' draws
        out[k] = v if locks.get(k) else clamp(lerp(v, r, a))
    return out


def preset_dumps(values):
    return json.dumps({k: round(float(v), 6) for k, v in sorted(values.items())}, sort_keys=True,
                      separators=(',', ':'))


def preset_loads(text):
    if not str(text).strip():
        return {}
    d = json.loads(text)
    if not isinstance(d, dict):
        raise ValueError('preset json must be an object')
    return {str(k): float(v) for k, v in d.items()}


def next_id(ids):
    ids = [int(i) for i in ids if str(i).strip().lstrip('-').isdigit()]
    return (max(ids) + 1) if ids else 1


def knob_name(i):
    return 'Knob{}'.format(int(i))


def lock_name(i):
    return 'Lock{}'.format(int(i))


def split_names(text):
    """'tx, ty  period' -> ['tx', 'ty', 'period'] (comma and/or space separated; wildcards kept)."""
    return [t for t in re.split(r'[\s,]+', str(text or '')) if t]


def ctrl_target(chan, binds):
    """Which knob a control-in channel drives. Matches a bind's src column first (e.g. 'ch1c21' from a MIDI mapper),
    then the knob name itself ('Knob3'), then 'k3' / '3'. Returns the knob name or None."""
    c = str(chan)
    for b in binds:
        if b.get('src') and str(b['src']) == c:
            return b['knob']
    knobs = set(b['knob'] for b in binds)
    if c in knobs:
        return c
    m = re.match(r'^(?:k|knob)?(\d+)$', c, re.I)
    if m and knob_name(m.group(1)) in knobs:
        return knob_name(m.group(1))
    return None


def cc_to_unit(v):
    return clamp(float(v) / 127.0)


def unit_to_cc(u):
    return int(round(clamp(float(u)) * 127))


def rows_to_dicts(rows):
    """[[header...], [row...]...] -> [dict]"""
    if not rows:
        return []
    head = [str(h) for h in rows[0]]
    return [dict(zip(head, [str(x) for x in r])) for r in rows[1:]]


def dicts_to_rows(items, cols):
    return [list(cols)] + [[str(d.get(c, '')) for c in cols] for d in items]


class Morph(object):
    """One running morph: start/end {knob: value}, duration, curve. A knob changed by hand mid-morph (its current
    value is not what the morph wrote last) drops out of the morph, so a touched knob is never fought."""

    def __init__(self, start, end, dur, curve_name='linear', t0=0.0, eps=1e-6):
        self.start, self.end = dict(start), dict(end)
        self.dur, self.curve, self.t0, self.eps = max(0.0, float(dur)), curve_name, float(t0), eps
        self.last = dict(start)
        self.dropped = set()

    def progress(self, now):
        if self.dur <= 0:
            return 1.0
        return clamp((float(now) - self.t0) / self.dur)

    def step(self, now, current=None):
        """-> ({knob: value to write}, done)."""
        if current:
            for k, v in current.items():
                if k in self.last and k not in self.dropped and abs(float(v) - self.last[k]) > 1e-4:
                    self.dropped.add(k)
        t = self.progress(now)
        k_ = curve(t, self.curve)
        out = {}
        for k, vb in self.end.items():
            if k in self.dropped:
                continue
            va = float(self.start.get(k, vb))
            out[k] = lerp(va, float(vb), k_)
            self.last[k] = out[k]
        return out, t >= 1.0
