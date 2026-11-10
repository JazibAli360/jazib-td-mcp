# cuelist_logic: pure logic of CQ_cuelist (cue list + timecode show control). No td import; tested offline in
# test/test_cuelist.py and copied into the COMP's `cq_logic` Text DAT by builders/cuelist.py.
# Spec: docs/research/BQ_show_control_timecode.md section 3 (clean-room). ASCII only.
import re

# ------------------------------------------------------------------ timecode maths
TC_RATES = {            # menu name -> (nominal fps, drop frame, real fps)
    '24': (24, False, 24.0), '25': (25, False, 25.0), '2997df': (30, True, 30000.0 / 1001.0),
    '30': (30, False, 30.0), '50': (50, False, 50.0), '60': (60, False, 60.0),
}
TC_RATE_NAMES = ['24', '25', '2997df', '30', '50', '60']
TC_RATE_LABELS = ['24', '25', '29.97 DF', '30', '50', '60']


def rate_info(name):
    return TC_RATES.get(str(name), TC_RATES['25'])


def tc_to_frames(h, m, s, f, fps_nom, df):
    total = (h * 3600 + m * 60 + s) * fps_nom + f
    if df:
        drop = 2 if fps_nom == 30 else 4
        mins = h * 60 + m
        total -= drop * (mins - mins // 10)
    return total


def frames_to_tc(n, fps_nom, df):
    n = int(n)
    if df:
        drop = 2 if fps_nom == 30 else 4
        per10 = fps_nom * 600 - drop * 9
        per1 = fps_nom * 60 - drop
        d, r = divmod(n, per10)
        n += 9 * drop * d + (drop * ((r - drop) // per1) if r > drop else 0)
    f = n % fps_nom
    s = (n // fps_nom) % 60
    m = (n // (fps_nom * 60)) % 60
    h = n // (fps_nom * 3600)
    return h, m, s, f


def seconds_of_frames(n, fps_nom, df):
    return n * 1001.0 / (fps_nom * 1000.0) if df else n / float(fps_nom)


def frames_of_seconds(t, fps_nom, df):
    real = fps_nom * 1000.0 / 1001.0 if df else float(fps_nom)
    return int(t * real + 1e-6)


_TC_RE = re.compile(r'^\s*(-?)(\d{1,2})[:;.](\d{1,2})[:;.](\d{1,2})[:;.](\d{1,3})\s*$')
_HM_RE = re.compile(r'^\s*(\d+)h(?:(\d+)m?)?\s*$')


def parse_tc(s, fps_nom=25, df=False):
    """'HH:MM:SS:FF' / 'HH:MM:SS;FF' / '1h30' / '01h30m' / '0100' (HHMM) / '100000' (HHMMSS) / '12.5s' -> seconds or None."""
    if s is None:
        return None
    s = str(s).strip().lower()
    if not s:
        return None
    m = _TC_RE.match(s)
    if m:
        sign, h, mi, se, fr = m.groups()
        h, mi, se, fr = int(h), int(mi), int(se), int(fr)
        if mi > 59 or se > 59 or fr >= fps_nom:
            return None
        v = seconds_of_frames(tc_to_frames(h, mi, se, fr, fps_nom, df), fps_nom, df)
        return -v if sign else v
    m = _HM_RE.match(s)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2) or 0)
        return None if mi > 59 else float(h * 3600 + mi * 60)
    if s.endswith('s'):
        try:
            return float(s[:-1])
        except ValueError:
            return None
    if s.isdigit() and len(s) in (4, 6):
        h, mi = int(s[0:2]), int(s[2:4])
        se = int(s[4:6]) if len(s) == 6 else 0
        if mi > 59 or se > 59:
            return None
        return float(h * 3600 + mi * 60 + se)
    return None


def fmt_tc(t, fps_nom=25, df=False):
    neg = t < 0
    h, m, s, f = frames_to_tc(frames_of_seconds(abs(t), fps_nom, df), fps_nom, df)
    return '%s%02d:%02d:%02d%s%02d' % ('-' if neg else '', h, m, s, ';' if df else ':', f)


# ------------------------------------------------------------------ curves
CURVES = ['cut', 'linear', 'ease', 'smooth']


def curve(u, name):
    u = 0.0 if u < 0 else 1.0 if u > 1 else u
    if name == 'cut':
        return 1.0 if u > 0 else 0.0
    if name == 'ease':
        return u * u * (3 - 2 * u)
    if name == 'smooth':
        return u * u * u * (u * (6 * u - 15) + 10)
    return u


# ------------------------------------------------------------------ cue table
COLUMNS = ['id', 'num', 'name', 'trigger', 'at', 'pre', 'fade', 'curve', 'kind', 'target', 'value', 'follow', 'delay',
           'note', 'enabled', 'color']
TRIGGERS = ('manual', 'follow', 'tc', 'bar', 'osc')
KINDS = ('zc_recall', 'zc_set', 'tl', 'par', 'osc', 'arena_osc', 'arena_rest', 'note', 'group')
STATE_KINDS = ('par', 'zc_set', 'zc_recall')      # kinds whose value is a look state (replayed by resolve_state)
FADE_KINDS = ('par', 'zc_set')                    # kinds faded by our own fader


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_cues(rows, fps_nom=25, df=False, default_fade=0.0, default_curve='linear'):
    """rows = [[header...], [cells...], ...] -> (groups, errors). Never raises.
    A group = all enabled rows with the same num (fire together); groups sorted by num then first table row."""
    errors = []
    if not rows:
        return [], errors
    head = [str(h).strip().lower() for h in rows[0]]
    if 'num' not in head:
        return [], ['header: no num column']
    by = {}
    order = []
    for i, r in enumerate(rows[1:], start=1):
        d = dict((head[k], str(r[k]).strip() if k < len(r) else '') for k in range(len(head)))
        if not any(d.values()):
            continue
        if d.get('enabled', '1').lower() in ('0', 'off', 'false', 'no'):
            continue
        try:
            num = float(d.get('num', ''))
        except ValueError:
            errors.append('row %d: bad num %r' % (i, d.get('num')))
            continue
        trig = (d.get('trigger') or 'manual').lower()
        if trig not in TRIGGERS:
            errors.append('row %d: bad trigger %r' % (i, trig))
            continue
        kind = (d.get('kind') or 'note').lower()
        if kind not in KINDS:
            errors.append('row %d: bad kind %r' % (i, kind))
            continue
        at = None
        if trig == 'tc':
            at = parse_tc(d.get('at'), fps_nom, df)
            if at is None:
                errors.append('row %d: bad tc %r' % (i, d.get('at')))
                continue
        elif trig in ('bar', 'osc'):
            errors.append('row %d: trigger %s needs the link/osc clock (not in v1), kept as manual' % (i, trig))
            trig = 'manual'
        fade = _f(d.get('fade'), None) if d.get('fade') else None
        cv = (d.get('curve') or '').lower() or default_curve
        if cv not in CURVES:
            errors.append('row %d: bad curve %r -> linear' % (i, cv))
            cv = 'linear'
        act = {'row': i, 'id': d.get('id') or str(i), 'kind': kind, 'target': d.get('target', ''),
               'value': d.get('value', ''), 'fade': default_fade if fade is None else max(0.0, fade), 'curve': cv}
        key = repr(num)
        if key not in by:
            by[key] = {'num': num, 'name': d.get('name') or ('%g' % num), 'trigger': trig, 'at': at,
                       'follow': (d.get('follow') or '').lower(), 'delay': max(0.0, _f(d.get('delay'))),
                       'first_row': i, 'actions': []}
            order.append(key)
        by[key]['actions'].append(act)
    groups = sorted((by[k] for k in order), key=lambda g: (g['num'], g['first_row']))
    for k, g in enumerate(groups):
        g['index'] = k
    return groups, errors


def state_key(a):
    return '%s:%s' % (a['kind'], a['target'])


def group_values(g):
    out = {}
    for a in g['actions']:
        if a['kind'] in STATE_KINDS:
            out[state_key(a)] = a['value']
    return out


def due_groups(groups, t):
    return [g for g in groups if g['trigger'] == 'tc' and g['at'] is not None and g['at'] <= t + 1e-9]


def resolve_state(groups, t, tracking=True):
    """Tracked look state at time t: replay timed cues with at <= t in time order."""
    state = {}
    for g in sorted(due_groups(groups, t), key=lambda g: (g['at'], g['num'])):
        if tracking:
            state.update(group_values(g))
        else:
            state = dict(group_values(g))
    return state


def find_group(groups, ref):
    ref = str(ref).strip()
    if not ref:
        return None
    try:
        n = float(ref)
        for g in groups:
            if abs(g['num'] - n) < 1e-9:
                return g['index']
    except ValueError:
        pass
    for g in groups:
        if g['name'].lower() == ref.lower():
            return g['index']
    return None


# ------------------------------------------------------------------ fader
class Fader(object):
    """Active fades by state key. tick(dt, rate) -> [(key, value)] written this tick; finished keys in .done."""

    def __init__(self):
        self.f = {}
        self.done = []

    def start(self, key, a, b, dur, cv, now=None):
        self.f[key] = {'a': float(a), 'b': float(b), 'dur': float(dur), 'el': 0.0, 'cv': cv, 'v': float(a), 't0': now}

    def current(self, key, default=None):
        e = self.f.get(key)
        return e['v'] if e else default

    def active(self):
        return bool(self.f)

    def longest_left(self, rate=1.0):
        if not self.f:
            return 0.0
        r = rate if rate > 0 else 1e-9
        return max((e['dur'] - e['el']) / r for e in self.f.values())

    def stop(self):
        self.f = {}

    def tick(self, dt, rate=1.0, now=None):
        out = []
        self.done = []
        for k in list(self.f):
            e = self.f[k]
            d = dt
            if now is not None and e.get('t0') is not None:   # first tick after a mid-frame start: count only
                d = min(dt, max(0.0, now - e['t0']))           # the time since the start, not the whole frame
                e['t0'] = None
            e['el'] += max(0.0, d) * max(0.0, rate)
            u = 1.0 if e['dur'] <= 0 else e['el'] / e['dur']
            e['v'] = e['a'] + (e['b'] - e['a']) * curve(u, e['cv'])
            out.append((k, e['v']))
            if u >= 1.0:
                e['v'] = e['b']
                out[-1] = (k, e['b'])
                del self.f[k]
                self.done.append(k)
        return out


# ------------------------------------------------------------------ chase (external clock lock)
class Chase(object):
    """Own clock slaved to an external source. States: chasing / locked / freewheel / lost."""

    def __init__(self, fps=25.0, lockwindow=3.0, freewheel=2.0, jump=1.0, stale=0.12, good_needed=5):
        self.fps, self.lockwindow, self.freewheel, self.jump, self.stale = fps, lockwindow, freewheel, jump, stale
        self.good_needed = good_needed
        self.reset()

    def reset(self):
        self.state = 'chasing'
        self.good = 0
        self.bad = 0
        self.speed = 1.0
        self.last_src = None
        self.since_change = 1e9
        self.fw = 0.0
        self.err = 0.0

    def step(self, own, src, dt):
        """-> (own', state, err, located). src None = no source."""
        located = False
        if src is not None and (self.last_src is None or abs(src - self.last_src) > 1e-9):
            if self.last_src is not None and dt > 0 and self.since_change < 0.5:
                inst = (src - self.last_src) / (self.since_change + dt)
                if -0.1 <= inst <= 4.0:
                    self.speed += (inst - self.speed) * 0.2
            self.last_src = src
            self.since_change = 0.0
        else:
            self.since_change += dt
        ok = src is not None and self.since_change <= self.stale
        win = self.lockwindow / max(1.0, self.fps)
        if ok:
            pred = own + dt * self.speed
            err = src - pred
            self.err = err
            self.fw = 0.0
            if err < -max(win, 2.0 / self.fps) or err > self.jump:
                self.good = 0
                self.state = 'locked' if self.state == 'locked' else 'chasing'
                return src, self.state, err, True
            if abs(err) < win:
                self.good += 1
                self.bad = 0
            else:
                self.good = 0
                self.bad += 1
            if self.state != 'locked' and self.good >= self.good_needed:
                self.state = 'locked'
            elif self.state == 'locked' and self.bad >= self.good_needed:
                self.state = 'chasing'
            elif self.state in ('freewheel', 'lost'):
                self.state = 'chasing'
            new = pred + err * 0.5
            if new < own and src >= own:
                new = own
            return new, self.state, err, located
        if self.state in ('locked', 'freewheel'):
            self.fw += dt
            if self.fw <= self.freewheel:
                self.state = 'freewheel'
                return own + dt * self.speed, self.state, self.err, False
            self.state = 'lost'
            self.good = 0
        return own, self.state, self.err, False


# ------------------------------------------------------------------ engine (GO / standby / queue / follow / tc)
class Engine(object):
    """State machine. Drain .out (actions) and .events after every call.
    out items: {'op': 'set', 'kind', 'target', 'value'} (state write) or {'op': 'fire', 'kind', 'target', 'value',
    'fade', 'curve', 'cue'} (one-shot executor action). events: (name, detail)."""

    def __init__(self, groups=None):
        self.fader = Fader()
        self.values = {}            # state key -> last value written (floats for faded kinds, strings otherwise)
        self.groups = []
        self.standby = 0
        self.running = None         # index of the last fired group
        self.queued = False
        self.pending = []           # [(due_time, index, why)]
        self.prev_t = None
        self.go_count = 0
        self.out = []
        self.events = []
        self.getter = None          # optional (kind, target) -> current float (the runtime reads the live par)
        self.set_groups(groups or [])

    # -- table
    def set_groups(self, groups):
        old = self.groups[self.standby]['num'] if self.groups and self.standby < len(self.groups) else None
        self.groups = groups
        self.standby = 0
        if old is not None:
            for g in groups:
                if g['num'] >= old - 1e-9:
                    self.standby = g['index']
                    break
            else:
                self.standby = len(groups)
        self.pending = [p for p in self.pending if p[1] < len(groups)]

    def drain(self):
        o, e = self.out, self.events
        self.out, self.events = [], []
        return o, e

    def _ev(self, name, detail=''):
        self.events.append((name, detail))

    # -- standby moves (no fire)
    def standby_next(self):
        self.standby = min(len(self.groups), self.standby + 1)
        self._ev('standby', self._name(self.standby))

    def standby_prev(self):
        self.standby = max(0, self.standby - 1)
        self._ev('standby', self._name(self.standby))

    def goto(self, ref):
        k = find_group(self.groups, ref)
        if k is None:
            self._ev('error', 'goto: no cue %r' % ref)
            return False
        self.standby = k
        self._ev('standby', self._name(k))
        return True

    def reset(self):
        self.standby = 0
        self.queued = False
        self.pending = []
        self._ev('reset', self._name(0))

    def stop(self):
        self.fader.stop()
        self.queued = False
        self.pending = []
        self._ev('stop', '')

    def _name(self, k):
        if 0 <= k < len(self.groups):
            g = self.groups[k]
            return '%g %s' % (g['num'], g['name'])
        return 'end'

    # -- firing
    def go(self, now=0.0, queuemode='queue'):
        if self.standby >= len(self.groups):
            self._ev('go_end', 'no standby cue')
            return False
        if self.fader.active():
            if queuemode == 'queue':
                self.queued = True
                self._ev('go_queued', self._name(self.standby))
                return False
            if queuemode == 'ignore':
                self._ev('go_ignored', self._name(self.standby))
                return False
        self.fire(self.standby, now, 'go')
        return True

    def goback(self, now=0.0):
        k = (self.running if self.running is not None else self.standby) - 1
        if k < 0:
            self._ev('error', 'goback: at first cue')
            return False
        self.fire(k, now, 'back')
        return True

    def fire(self, k, now=0.0, why='go', rate=1.0):
        g = self.groups[k]
        self.go_count += 1
        self.running = k
        self.standby = k + 1
        self._ev('fire', '%s (%s)' % (self._name(k), why))
        for a in g['actions']:
            kind = a['kind']
            if kind in FADE_KINDS:
                key = state_key(a)
                b = _f(a['value'], None)
                if b is None:
                    self._ev('error', 'cue %g: value %r not a number' % (g['num'], a['value']))
                    continue
                if a['fade'] > 0 and a['curve'] != 'cut':
                    cur = self.fader.current(key, None)
                    if cur is None:
                        cur = _f(self.values.get(key), None)
                    if cur is None and self.getter is not None:
                        cur = self.getter(kind, a['target'])
                    if cur is None:
                        cur = 0.0
                    self.fader.start(key, cur, b, a['fade'], a['curve'], now)
                    self._ev('fade_start', '%s -> %g over %gs' % (key, b, a['fade']))
                else:
                    self.fader.f.pop(key, None)
                    self.values[key] = b
                    self.out.append({'op': 'set', 'kind': kind, 'target': a['target'], 'value': b})
            else:
                if kind in STATE_KINDS:
                    self.values[state_key(a)] = a['value']
                self.out.append({'op': 'fire', 'kind': kind, 'target': a['target'], 'value': a['value'],
                                 'fade': a['fade'], 'curve': a['curve'], 'cue': g['num']})
        # follow chain (Autofollow is applied by tick's caller via the follow flag on the next group)
        nxt = k + 1
        if nxt < len(self.groups):
            n = self.groups[nxt]
            if n['trigger'] == 'follow':
                if n['follow'] == 'continue':
                    self.pending.append((now + self.fader.longest_left(rate) + n['delay'], nxt, 'continue'))
                else:
                    self.pending.append((now + n['delay'], nxt, 'follow'))

    def locate(self, t, tracking=True):
        self.fader.stop()
        self.queued = False
        self.pending = []
        st = resolve_state(self.groups, t, tracking)
        for key, v in st.items():
            kind, target = key.split(':', 1)
            if kind in FADE_KINDS:
                v = _f(v, 0.0)
            self.values[key] = v
            self.out.append({'op': 'set', 'kind': kind, 'target': target, 'value': v})
        due = due_groups(self.groups, t)
        last = max((g['index'] for g in due), default=-1)
        self.standby = last + 1
        self.running = last if last >= 0 else None
        self._ev('locate', '%.3f s, %d targets' % (t, len(st)))

    def tick(self, now, dt, rate=1.0, clock_t=None, clock_ok=False, jump=1.0, autofollow=True, tracking=True,
             queuemode='queue'):
        # fades
        for key, v in self.fader.tick(dt, rate, now):
            kind, target = key.split(':', 1)
            self.values[key] = v
            self.out.append({'op': 'set', 'kind': kind, 'target': target, 'value': v})
        for key in self.fader.done:
            self._ev('fade_end', key)
        if self.queued and not self.fader.active():
            self.queued = False
            self.go(now, queuemode)
        # follow chain
        if self.pending:
            due = [p for p in self.pending if p[0] <= now + 1e-9]
            self.pending = [p for p in self.pending if p[0] > now + 1e-9]
            for _, k, why in sorted(due):
                if autofollow:
                    self.fire(k, now, why, rate)
        # timecode triggers
        if clock_t is not None:
            prev = self.prev_t
            self.prev_t = clock_t
            if prev is None:                     # first tick: only land on the state if timed cues are due
                if clock_ok and due_groups(self.groups, clock_t):
                    self.locate(clock_t, tracking)
            elif clock_ok:
                step = clock_t - prev
                if step < -1e-9 or step > jump:
                    self.locate(clock_t, tracking)
                elif step > 0:
                    for g in self.groups:
                        if g['trigger'] == 'tc' and prev < g['at'] - 1e-9 <= clock_t:
                            self.fire(g['index'], now, 'tc', rate)


# ------------------------------------------------------------------ log ring
LOG_HEAD = ['wall', 'tc', 'clock', 'event', 'detail']


class LogRing(object):
    def __init__(self, maxn=500):
        self.maxn = max(1, int(maxn))
        self.rows = []

    def add(self, row):
        self.rows.append(row)
        if len(self.rows) > self.maxn:
            del self.rows[:len(self.rows) - self.maxn]

    def clear(self):
        self.rows = []


def csv_line(cells):
    out = []
    for c in cells:
        s = str(c)
        if any(ch in s for ch in ',"\n'):
            s = '"' + s.replace('"', '""') + '"'
        out.append(s)
    return ','.join(out) + '\n'
