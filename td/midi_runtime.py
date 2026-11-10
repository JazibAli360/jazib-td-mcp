"""jazib_midi runtime: the TD side of our own MIDI mapping system (Text DAT <jazib_midi>/runtime).

Source of truth: td/midi_runtime.py on disk; `td_midi_build` copies it (and td/midi_core.py) into the COMP, so the
COMP keeps working when the .toe is opened without the MCP. Every entry point takes the jazib_midi COMP `c`:

  MIDI In DAT callbacks (midi_cb)  -> on_receive(c, message, channel, index, value, bytes)
  Execute DAT tick (Frame Start)   -> on_frame(c)      smoothing, learn window, 10 Hz par poll -> takeover reset + feedback
  Parameter Execute DAT (par_exec) -> on_par(c, name)  Learn / Activebank / Sendfeedback / Openeditor / Refreshdevices
  editor list callbacks (list_cb)  -> editor_cell / editor_edit / editor_select
  td_midi_* commands (handlers.py) -> the same functions; td_midi_simulate builds the raw bytes and calls on_receive,
                                      so a simulated message takes exactly the path of a real one.

Data lives in plain tables (bindings = midi_core.to_rows, config = key/value, events = last messages); transient
engine state (takeover, relative accumulators, smoothing) lives in the module dict _ST, never in op storage (T-67).
Pure ASCII. Uses midi_core (lane A) for every value decision; this file only does TD I/O.
"""
import json
import time

EVENTS_HEADER = ['t', 'src', 'message', 'kind', 'ch', 'num', 'raw', 'hits', 'note']
EVENTS_CAP = 100          # rows kept in the events table (newest last)
POLL_FRAMES = 6           # par poll every 6 frames = 10 Hz at 60 fps
LEARN_WINDOW_S = 0.5      # learn: classify this long after the first message
LEARN_MAX_EVENTS = 12     # ... or as soon as this many arrived
LEARN_TIMEOUT_S = 30.0
DEVICE_TABLE = '/local/midi/device'
CONFIG_KEYS = ('version', 'device', 'active_bank', 'learn_state', 'learn_mode', 'learn_target', 'learn_par',
               'learn_id', 'learn_opts', 'learn_started', 'learn_first', 'learn_result', 'learn_note', 'last_error')
EDITOR_COLS = ['id', 'label', 'bank', 'msg', 'target.par', 'min', 'max', 'curve', 'mode', 'takeover', 'smooth',
               'fb', 'learn', 'del']
EDITOR_WIDTHS = [44, 108, 40, 92, 232, 48, 48, 66, 92, 64, 46, 26, 36, 28]  # 970 px: all 14 fit the 1000 px list
EDITOR_EDITABLE = ('label', 'bank', 'target.par', 'min', 'max', 'curve', 'mode', 'takeover', 'smooth', 'fb')
_ST = {}                  # comp path -> transient engine state


# ================================================================== pure helpers (no TD)

def decode_bytes(b):
    """Raw MIDI bytes (bytes, bytearray, list of ints, or a hex string 'b0 07 40') -> list of ints."""
    if b is None:
        return []
    if isinstance(b, str):
        out = []
        for tok in b.replace(',', ' ').split():
            try:
                out.append(int(tok, 16))
            except ValueError:
                return []
        return out
    try:
        return [int(x) & 255 for x in b]
    except (TypeError, ValueError):
        return []


def event_args(data):
    """Raw bytes of one message -> (kind, channel, number, value, value2) for midi_core.parse_event, or None."""
    if not data or data[0] < 0x80:
        return None
    st, ch = data[0] & 0xF0, (data[0] & 0x0F) + 1
    d1 = data[1] if len(data) > 1 else 0
    d2 = data[2] if len(data) > 2 else 0
    if st == 0xB0:
        return ('cc', ch, d1, d2, None)
    if st == 0x90:
        return ('noteon' if d2 > 0 else 'noteoff', ch, d1, d2, None)
    if st == 0x80:
        return ('noteoff', ch, d1, 0, None)
    if st == 0xE0:
        return ('pitchbend', ch, 0, d1, d2)  # wire order: LSB, MSB
    if st == 0xA0:
        return ('aftertouch', ch, d1, d2, None)
    if st == 0xD0:
        return ('aftertouch', ch, -1, d1, None)
    if st == 0xC0:
        return ('program', ch, d1, 0, None)
    return None  # sysex, clock, sense...


def sim_bytes(kind, channel, number=0, value=0, value2=None):
    """Raw MIDI messages for one simulated event (what a controller would send). cc14 = MSB then LSB CC."""
    ch = (max(1, min(16, int(channel or 1))) - 1)
    k = str(kind).lower()
    n, v = int(number or 0) & 127, int(value or 0)
    if k == 'cc':
        return [[0xB0 | ch, n, v & 127]]
    if k == 'cc14':
        v14 = v * 128 + int(value2) if value2 is not None else v
        return [[0xB0 | ch, n, (v14 >> 7) & 127], [0xB0 | ch, n + 32, v14 & 127]]
    if k in ('note', 'noteon'):
        return [[0x90 | ch, n, v & 127]]
    if k == 'noteoff':
        return [[0x80 | ch, n, 0]]
    if k == 'pitchbend':
        if value2 is not None:
            lsb, msb = v & 127, int(value2) & 127
        else:
            v14 = max(0, min(16383, v + 8192 if v < 0 else v))
            lsb, msb = v14 & 127, v14 >> 7
        return [[0xE0 | ch, lsb, msb]]
    if k == 'aftertouch':
        if number is None or int(number) < 0:
            return [[0xD0 | ch, v & 127]]
        return [[0xA0 | ch, n, v & 127]]
    if k == 'program':
        return [[0xC0 | ch, n]]
    raise ValueError('unknown kind %r (cc, cc14, note, noteoff, pitchbend, aftertouch, program)' % kind)


def msg_text(m):
    k = m.get('kind', '')
    ch = 'any' if not m.get('channel') else 'ch%d' % m['channel']
    if k in ('pitchbend', 'program'):
        return '%s %s' % (k, ch)
    return '%s %s #%s' % (k, ch, m.get('number'))


def truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(v)


def _num(s, default=None):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


# ================================================================== TD I/O helpers

def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def core(c):
    d = c.op('midi_core')
    if d is None:
        raise RuntimeError('%s has no midi_core DAT: run td_midi_build' % c.path)
    return d.module


def state(c):
    s = _ST.get(c.path)
    if s is None:
        k = core(c)
        s = {'to': k.TakeoverState(), 'rel': {}, 'smooth': {}, 'last': {}, 'frame': 0, 'tlast': None,
             'sent': [], 'cache': (None, []), 'j14': (None, None), 'learn': [], 'hover': None, 'writes': 0}
        _ST[c.path] = s
    return s


def reset_state(c):
    _ST.pop(c.path, None)


def _table(c, name):
    t = c.op(name)
    if t is None:
        raise RuntimeError('%s has no %s table: run td_midi_build' % (c.path, name))
    return t


def _rows(t):
    return [[cell.val for cell in row] for row in t.rows()]


def cfg(c, key, default=''):
    t = c.op('config')
    if t is None:
        return default
    cell = _try(lambda: t[key, 1])
    return default if cell is None else cell.val


def set_cfg(c, key, value):
    t = _table(c, 'config')
    v = '' if value is None else str(value)
    if _try(lambda: t[key, 1]) is None:
        t.appendRow([key, v])
    else:
        t[key, 1] = v


def ensure_header(t, header):
    """A header row on top of a table. Live 31550: a new Table DAT holds one blank cell, not zero rows, so a
    `numRows == 0` check never wrote the header (events showed blank column names). Blank rows go."""
    if t is None:
        return
    rows = _rows(t)
    if rows and [str(x) for x in rows[0][:len(header)]] == list(header):
        return
    keep = [r for r in rows if any(str(x).strip() for x in r)]
    t.clear()
    t.appendRow(list(header))
    for r in keep:
        t.appendRow(r)


def init_config(c, device=''):
    ensure_header(c.op('events'), EVENTS_HEADER)
    ensure_header(c.op('bindings'), core(c).to_rows([])[0])
    t = _table(c, 'config')
    if t.numRows < 1 or _try(lambda: t[0, 0].val) != 'key':
        t.clear()
        t.appendRow(['key', 'value'])
    for k in CONFIG_KEYS:
        if _try(lambda: t[k, 1]) is None:
            t.appendRow([k, ''])
    set_cfg(c, 'version', getattr(core(c), 'VERSION', 1))
    set_cfg(c, 'active_bank', active_bank(c))
    if device:
        set_cfg(c, 'device', device)


def _par(c, name, default=None):
    p = _try(lambda: c.par[name])
    if p is None:
        return default
    return _try(p.eval, default)


def enabled(c):
    return truthy(_par(c, 'Enable', True))


def active_bank(c):
    b = _par(c, 'Activebank', None)
    if b is None:
        b = _num(cfg(c, 'active_bank', ''), 1)
    return int(b or 1)


def mappings(c):
    """Mappings from the bindings table (parsed once per table change)."""
    t = _table(c, 'bindings')
    text = t.text
    s = state(c)
    if s['cache'][0] != text:
        ms = core(c).from_rows(_rows(t)) if t.numRows else []
        s['cache'] = (text, ms)
        s['j14'] = (None, None)
    return [dict(m) for m in s['cache'][1]]


def write_mappings(c, ms):
    t = _table(c, 'bindings')
    t.clear()
    for r in core(c).to_rows(ms):
        t.appendRow(r)
    state(c)['cache'] = (None, [])
    _try(lambda: refresh_editor(c))


def find(c, mid):
    for m in mappings(c):
        if m['id'] == mid:
            return m
    return None


def resolve(c, m):
    """(op, par) of a mapping's target, or (None, None). Relative targets resolve from the COMP's parent."""
    tgt, pn = m.get('target') or '', m.get('par') or ''
    if not tgt or not pn:
        return None, None
    o = c.op(tgt) if tgt.startswith('/') else _try(lambda: c.parent().op(tgt))
    if o is None:
        return None, None
    p = _try(lambda: o.par[pn])
    return (o, p) if p is not None else (o, None)


def par_style(p):
    st = str(_try(lambda: p.style, 'Float') or 'Float')
    n = len(_try(lambda: list(p.menuNames), []) or []) if st in ('Menu', 'StrMenu') else None
    return st, (n or None)


def _exported(p):
    return str(_try(lambda: p.mode, '')).upper().endswith('EXPORT')


def _quantum(m, style, menu_count):
    if style in ('Menu', 'StrMenu') and menu_count and menu_count > 1:
        return 1.0 / (menu_count - 1)
    if style == 'Int':
        span = abs(m['max'] - m['min'])
        return 1.0 / span if span else 0.0
    return 0.0


def current_norm(c, m, p):
    st, n = par_style(p)
    v = _try(lambda: p.eval(), 0)
    if st in ('Menu', 'StrMenu') and n:
        v = _try(lambda: p.menuIndex, 0)
    return core(c).from_par_value(m, v, st, n)


def write_norm(c, m, p, norm):
    """Write a par from a norm (midi_core.to_par_value); returns the value written (Pulse: True when pulsed)."""
    st, n = par_style(p)
    v = core(c).to_par_value(m, norm, st, n)
    if st == 'Pulse':
        if v:
            p.pulse()
        return v
    if st in ('Menu', 'StrMenu') and n:
        p.menuIndex = int(v)
    else:
        p.val = v
    s = state(c)
    s['last'][m['id']] = _try(lambda: p.eval(), v)
    s['writes'] += 1
    return v


def _error(c, msg):
    _try(lambda: set_cfg(c, 'last_error', '%s %s' % (time.strftime('%H:%M:%S'), str(msg)[:300])))


def _log_event(c, src, message, ev, hits, note=''):
    t = c.op('events')
    if t is None:
        return
    if t.numRows < 1 or _try(lambda: t[0, 0].val) != EVENTS_HEADER[0]:
        ensure_header(t, EVENTS_HEADER)
    t.appendRow(['%.3f' % time.time(), src, str(message or '')[:24], ev.get('kind', '') if ev else '',
                 ev.get('channel', '') if ev else '', ev.get('number', '') if ev else '',
                 ev.get('raw', '') if ev else '', ' '.join(hits), note[:120]])
    while t.numRows > EVENTS_CAP + 1:
        t.deleteRow(1)


# ================================================================== MIDI in

def on_receive(c, message=None, channel=None, index=None, value=None, raw=None, source='midi'):
    """One message from the MIDI In DAT callback (or td_midi_simulate). Decodes the raw bytes when there are
    any (independent of TD's message text and index base), else falls back to midi_core.parse_midiin_row.
    Returns {events, writes, learn?}. Never raises inside TD's callback: errors land in config last_error."""
    out = {'events': [], 'writes': []}
    try:
        k = core(c)
        data = decode_bytes(raw)
        args = event_args(data) if data else None
        if args is not None:
            ev = k.parse_event(*args)
        elif data:
            ev = None  # sysex / clock: ignored
        else:
            ev = k.parse_midiin_row({'message': message, 'channel': channel, 'index': index, 'value': value})
        if ev is None:
            return out
        evs = [ev]
        if ev['kind'] == 'cc':
            j = joiner(c)
            if j is not None and j.wants(ev['number']):
                e14 = j.feed_event(ev)
                if e14 is not None:
                    evs.append(e14)
        for e in evs:
            r = handle_event(c, e, message, source)
            out['events'].append(e)
            out['writes'] += r.get('writes', [])
            if r.get('learn'):
                out['learn'] = r['learn']
    except Exception as e:  # keep the engine alive; the error is visible in config + td_midi_status
        _error(c, '%s: %s' % (type(e).__name__, e))
        out['error'] = '%s: %s' % (type(e).__name__, e)
    return out


def joiner(c):
    ms = mappings(c)
    nums = tuple(sorted({m['number'] for m in ms if m['kind'] == 'cc14'}))
    s = state(c)
    if not nums:
        return None
    if s['j14'][0] != nums:
        s['j14'] = (nums, core(c).Cc14Joiner(numbers=nums))
    return s['j14'][1]


def handle_event(c, ev, message='', source='midi'):
    s = state(c)
    if cfg(c, 'learn_state') == 'listening':
        if ev['kind'] != 'cc14':  # classify_learn joins 14-bit pairs itself
            s['learn'].append(ev)
            if not cfg(c, 'learn_first'):
                set_cfg(c, 'learn_first', '%.3f' % time.time())
            if cfg(c, 'learn_mode') == 'hover':
                hp = hover_par(c)
                if hp is not None:
                    s['hover'] = (hp.owner.path, hp.name)
        _log_event(c, source, message, ev, [], 'learn')
        r = {'writes': []}
        if len(s['learn']) >= LEARN_MAX_EVENTS:
            r['learn'] = learn_finish(c)
        return r
    if not enabled(c):
        _log_event(c, source, message, ev, [], 'disabled')
        return {'writes': []}
    k = core(c)
    bank = active_bank(c)
    writes, notes = [], []
    for m in mappings(c):
        if not k.matches(m, ev, bank):
            continue
        o, p = resolve(c, m)
        if p is None:
            if m.get('target'):
                notes.append('%s: no %s.%s' % (m['id'], m['target'], m['par']))
            continue
        if _exported(p):
            notes.append('%s: %s is exported (driven elsewhere), skipped' % (m['id'], m['par']))
            continue
        st, n = par_style(p)
        cur = current_norm(c, m, p)
        new = k.step_value(m, ev, cur, s, _quantum(m, st, n))
        if new is None:
            continue
        allow, outn = k.takeover_gate(m, s['to'], new, cur)
        if not allow:
            notes.append('%s: waiting for pickup' % m['id'])
            continue
        if m.get('smooth') and float(m['smooth']) > 0 and st not in ('Pulse', 'Toggle', 'Momentary'):
            sm = s['smooth'].get(m['id'])
            s['smooth'][m['id']] = [sm[0] if sm else cur, outn]
            writes.append({'id': m['id'], 'par': '%s.%s' % (o.path, p.name), 'smoothing_to': outn})
            continue
        v = write_norm(c, m, p, outn)
        writes.append({'id': m['id'], 'par': '%s.%s' % (o.path, p.name), 'value': v})
        if m['mode'] in k.RELATIVE_MODES or m['mode'] == 'toggle':  # LED ring / button light follows our own write
            send_feedback(c, m, outn)
    _log_event(c, source, message, ev, [w['id'] for w in writes], '; '.join(notes))
    return {'writes': writes, 'notes': notes}


def hover_par(c):
    """ui.rolloverPar when it is a par outside this COMP (the par the user hovers while moving a control)."""
    try:
        import td
        p = td.ui.rolloverPar
    except Exception:
        return None
    if p is None:
        return None
    owner = _try(lambda: p.owner)
    if owner is None or str(owner.path).startswith(c.path + '/') or owner.path == c.path:
        return None
    return p


# ================================================================== frame tick

def on_frame(c, frame=None):
    try:
        s = state(c)
        now = time.time()
        dt = (now - s['tlast']) if s['tlast'] else 1.0 / 60.0
        s['tlast'] = now
        s['frame'] += 1
        mi = c.op('midi_in')  # unviewed DATs do not cook: keep the MIDI In DAT cooking while enabled
        if mi is not None and enabled(c):
            _try(lambda: mi.cook(force=True))
        if s['smooth']:
            _step_smooth(c, s, dt)
        ls = cfg(c, 'learn_state')
        if ls == 'listening':
            first = _num(cfg(c, 'learn_first'), None)
            started = _num(cfg(c, 'learn_started'), now)
            if first is not None and now - first >= LEARN_WINDOW_S:
                learn_finish(c)
            elif first is None and now - started >= LEARN_TIMEOUT_S:
                set_cfg(c, 'learn_state', 'timeout')
                _try(lambda: refresh_editor(c))
        if s['frame'] % POLL_FRAMES == 0:
            poll(c)
    except Exception as e:
        _error(c, 'on_frame %s: %s' % (type(e).__name__, e))


def _step_smooth(c, s, dt):
    k = core(c)
    byid = dict((m['id'], m) for m in mappings(c))
    for mid in list(s['smooth']):
        cur, target = s['smooth'][mid]
        m = byid.get(mid)
        o, p = resolve(c, m) if m else (None, None)
        if p is None:
            s['smooth'].pop(mid)
            continue
        v = k.smooth(cur, target, dt, float(m['smooth']))
        if abs(v - target) <= 1e-4:
            v = target
            s['smooth'].pop(mid)
        else:
            s['smooth'][mid] = [v, target]
        write_norm(c, m, p, v)


def poll(c):
    """10 Hz: a mapped par changed by something else (slider, preset, other MIDI) -> takeover reset + feedback."""
    s = state(c)
    k = core(c)
    bank = active_bank(c)
    fb = feedback_on(c)
    for m in k.select_bank(mappings(c), bank):
        o, p = resolve(c, m)
        if p is None:
            continue
        v = _try(lambda: p.eval())
        if m['id'] not in s['last']:
            s['last'][m['id']] = v
            continue
        if v != s['last'][m['id']]:
            s['last'][m['id']] = v
            k.takeover_reset(s['to'], m['id'])
            if fb:
                send_feedback(c, m, current_norm(c, m, p))


# ================================================================== MIDI out (feedback)

def feedback_on(c):
    return truthy(_par(c, 'Feedback', True)) and enabled(c)


def send_feedback(c, m, norm):
    if not feedback_on(c):
        return []
    msgs = core(c).feedback_messages(m, norm)
    if msgs:
        send(c, msgs)
    return msgs


def send(c, msgs):
    """[(kind, ch, num, val)] through the MIDI Out CHOP (raw 0..127 values; onebased off, normalize off at build)."""
    o = c.op('midi_out')
    s = state(c)
    for kind, ch, num, val in msgs:
        s['sent'].append([kind, ch, num, val])
        if o is None:
            continue
        try:
            if kind == 'cc':
                o.sendControl(ch, num, val)
            elif kind == 'note':
                if val > 0:
                    o.sendNoteOn(ch, num, val)
                else:
                    o.sendNoteOff(ch, num, 0)
            elif kind == 'pitchbend':
                o.sendPitchBend(ch, val)
            elif kind == 'aftertouch':
                if num is not None and num >= 0:
                    o.sendPolyKeyPressure(ch, num, val)
                else:
                    o.sendChannelPressure(ch, val)
            s['send_error'] = None
        except Exception as e:
            # live 31550: with no device behind the MIDI Out CHOP every send* raises tdError('Cannot communicate
            # with the MIDI device.'); feedback must never abort the write / the other mappings / the frame tick
            msg = 'feedback not sent: %s: %s' % (type(e).__name__, e)
            if s.get('send_error') != msg:  # one config write per new error, not one per message
                s['send_error'] = msg
                _error(c, msg)
    del s['sent'][:-50]


def send_all_feedback(c):
    n = 0
    k = core(c)
    for m in k.select_bank(mappings(c), active_bank(c)):
        o, p = resolve(c, m)
        if p is not None:
            n += len(send_feedback(c, m, current_norm(c, m, p)))
    return n


# ================================================================== mappings API (handlers + editor)

def par_defaults(c, target, par):
    """min/max/default/mode hints from the target par (normMin/normMax, menu size, toggle/pulse)."""
    o, p = resolve(c, {'target': target, 'par': par})
    if p is None:
        return {}
    st, n = par_style(p)
    d = {}
    if st in ('Menu', 'StrMenu') and n:
        d.update(min=0.0, max=float(max(1, n - 1)))
    elif st in ('Toggle', 'Momentary', 'Pulse'):
        d.update(min=0.0, max=1.0)
    else:
        lo, hi = _num(_try(lambda: p.normMin), 0.0), _num(_try(lambda: p.normMax), 1.0)
        if lo == hi:
            hi = lo + 1.0
        d.update(min=float(lo), max=float(hi))
        dv = _num(_try(lambda: p.default), None)
        if dv is not None:
            d['default'] = dv
    d['style'] = st
    return d


def button_mode(style):
    return {'Pulse': 'trigger', 'Momentary': 'momentary'}.get(style, 'toggle')


def put_mapping(c, fields):
    """Add (no id / unknown id) or update (known id: fields merged) one mapping; validated by midi_core.
    min/max default to the target par's normMin/normMax. Returns the stored mapping."""
    k = core(c)
    fields = dict((a, b) for a, b in dict(fields).items() if b is not None)
    bad = [f for f in fields if f not in k.DEFAULTS]
    if bad:
        raise ValueError('unknown mapping field(s) %s (fields: %s)' % (bad, ', '.join(k.FIELDS)))
    ms = mappings(c)
    old = None
    for m in ms:
        if fields.get('id') and m['id'] == fields['id']:
            old = m
    if old is not None:
        base = dict(old)
        retarget = any(f in fields for f in ('target', 'par'))
    else:
        base = {}
        retarget = True
        if 'bank' not in fields:
            fields['bank'] = active_bank(c)
    if retarget and fields.get('target', base.get('target')) and fields.get('par', base.get('par')):
        d = par_defaults(c, fields.get('target', base.get('target')), fields.get('par', base.get('par')))
        if not d:
            raise ValueError('no parameter %s on %s' % (fields.get('par', base.get('par')),
                                                         fields.get('target', base.get('target'))))
        for key in ('min', 'max', 'default'):
            if key in d and key not in fields:
                fields[key] = d[key]
    base.update(fields)
    if not base.get('id'):
        base['id'] = k.next_id(ms)
    if not base.get('label') and base.get('par'):
        base['label'] = '%s.%s' % (str(base.get('target', '')).rsplit('/', 1)[-1], base['par'])
    m = k.new_mapping(**base)
    errs = k.validate(m)
    if errs:
        raise ValueError('mapping %s invalid: %s' % (m['id'], '; '.join(errs)))
    ms = [x for x in ms if x['id'] != m['id']] + [m] if old is None else [m if x['id'] == m['id'] else x for x in ms]
    write_mappings(c, ms)
    s = state(c)
    k.takeover_reset(s['to'], m['id'])
    s['rel'].pop(m['id'], None)
    s['last'].pop(m['id'], None)
    return m


def remove(c, ids):
    ids = set(ids)
    ms = mappings(c)
    gone = [m['id'] for m in ms if m['id'] in ids]
    write_mappings(c, [m for m in ms if m['id'] not in ids])
    for i in gone:
        core(c).takeover_reset(state(c)['to'], i)
        state(c)['smooth'].pop(i, None)
    return gone


def set_bank(c, bank):
    bank = int(bank)
    if bank < 1:
        raise ValueError('active bank must be >= 1 (bank 0 = mappings that are always live)')
    p = _try(lambda: c.par['Activebank'])
    if p is not None and _try(p.eval) != bank:
        p.val = bank  # par_exec calls on_bank too; harmless twice
    on_bank(c)
    return bank


def on_bank(c):
    s = state(c)
    core(c).takeover_reset(s['to'], None)
    s['smooth'].clear()
    s['last'].clear()
    set_cfg(c, 'active_bank', active_bank(c))
    if feedback_on(c):
        send_all_feedback(c)
    _try(lambda: refresh_editor(c))


def apply_preset(c, name, bank=None):
    k = core(c)
    if name not in k.CONTROLLER_PRESETS:
        raise ValueError('unknown preset %r (have: %s)' % (name, ', '.join(sorted(k.CONTROLLER_PRESETS))))
    ms = mappings(c)
    new = k.mappings_from_preset(name, bank=int(bank if bank is not None else active_bank(c)), existing=ms)
    write_mappings(c, ms + new)
    return new


def to_json_text(c):
    return core(c).to_json(mappings(c), active_bank=active_bank(c))


def load_json_text(c, text, merge=False):
    k = core(c)
    data = k.from_json(text)
    bad = [(m['id'], k.validate(m)) for m in data['mappings']]
    bad = [b for b in bad if b[1]]
    if bad:
        raise ValueError('invalid mappings in file: %s' % '; '.join('%s: %s' % (i, ', '.join(e)) for i, e in bad[:5]))
    ms = data['mappings']
    if merge:
        keep = dict((m['id'], m) for m in mappings(c))
        for m in ms:
            keep[m['id']] = m
        ms = list(keep.values())
    write_mappings(c, ms)
    s = state(c)
    k.takeover_reset(s['to'], None)
    s['last'].clear()
    s['smooth'].clear()
    if data.get('active_bank'):
        _try(lambda: set_bank(c, data['active_bank']))
    return {'mappings': len(ms), 'active_bank': active_bank(c)}


# ================================================================== learn

def learn_start(c, mode='par', target='', par='', mapping_id='', opts=None):
    """mode par: bind target.par to the next control moved. hover: the par under the mouse (ui.rolloverPar) while
    the control moves. slot: re-learn the message of an existing mapping (mapping_id)."""
    if mode not in ('par', 'hover', 'slot'):
        raise ValueError("learn mode must be par, hover or slot")
    if mode == 'par' and resolve(c, {'target': target, 'par': par})[1] is None:
        raise ValueError('no parameter %s on %s' % (par, target))
    if mode == 'slot' and find(c, mapping_id) is None:
        raise ValueError('no mapping %r' % mapping_id)
    s = state(c)
    s['learn'] = []
    s['hover'] = None
    for key, v in (('learn_state', 'listening'), ('learn_mode', mode), ('learn_target', target or ''),
                   ('learn_par', par or ''), ('learn_id', mapping_id or ''), ('learn_opts', json.dumps(opts or {})),
                   ('learn_started', '%.3f' % time.time()), ('learn_first', ''), ('learn_result', ''),
                   ('learn_note', '')):
        set_cfg(c, key, v)
    _try(lambda: refresh_editor(c))
    return learn_status(c)


def learn_stop(c):
    if cfg(c, 'learn_state') == 'listening':
        set_cfg(c, 'learn_state', 'stopped')
    state(c)['learn'] = []
    _try(lambda: refresh_editor(c))
    return learn_status(c)


def learn_finish(c):
    """Classify the collected messages (midi_core.classify_learn) and create / rebind the mapping now."""
    s = state(c)
    evs = list(s['learn'])
    if not evs:
        return learn_status(c)
    k = core(c)
    cl = k.classify_learn(evs) or {}
    mode = cfg(c, 'learn_mode')
    opts = _try(lambda: json.loads(cfg(c, 'learn_opts') or '{}'), {}) or {}
    msg = dict((f, cl[f]) for f in ('kind', 'channel', 'number', 'mode') if f in cl)
    s['learn'] = []
    try:
        if mode == 'slot':
            fields = dict(msg, id=cfg(c, 'learn_id'))
        else:
            if mode == 'hover':
                if s['hover'] is None:
                    set_cfg(c, 'learn_first', '')
                    set_cfg(c, 'learn_note', 'no parameter under the mouse: hover one while moving the control')
                    return learn_status(c)
                target, par = s['hover']
            else:
                target, par = cfg(c, 'learn_target'), cfg(c, 'learn_par')
            d = par_defaults(c, target, par)
            if cl.get('control') == 'button':
                msg['mode'] = button_mode(d.get('style'))
            fields = dict(msg, target=target, par=par)
            for m in mappings(c):  # one binding per target par and bank: re-learn replaces it
                if m['target'] == target and m['par'] == par and m['bank'] == int(opts.get('bank', active_bank(c))):
                    fields['id'] = m['id']
        fields.update(dict((a, b) for a, b in opts.items() if a in k.DEFAULTS and a != 'id'))
        m = put_mapping(c, fields)
        set_cfg(c, 'learn_state', 'done')
        set_cfg(c, 'learn_result', m['id'])
        set_cfg(c, 'learn_note', '%s (%s)' % (msg_text(m), cl.get('control', '')))
    except Exception as e:
        set_cfg(c, 'learn_state', 'error')
        set_cfg(c, 'learn_note', str(e)[:200])
    _try(lambda: refresh_editor(c))
    return learn_status(c)


def learn_status(c):
    r = dict((k[6:], cfg(c, k)) for k in ('learn_state', 'learn_mode', 'learn_target', 'learn_par', 'learn_id',
                                          'learn_result', 'learn_note'))
    r['events'] = len(state(c)['learn'])
    if r['result']:
        m = find(c, r['result'])
        if m is not None:
            r['mapping'] = m
    return r


# ================================================================== status / monitor

def devices(c):
    """Rows of TD's MIDI device table (Dialogs > MIDI Device Mapper) as dicts, plus menu names/labels."""
    t = c.op(DEVICE_TABLE)
    rows = _rows(t) if t is not None else []
    out = []
    if rows:
        head = rows[0]
        for r in rows[1:]:
            out.append(dict(zip(head, r)))
    return out


def device_menu(devs):
    names, labels = [], []
    for i, d in enumerate(devs):
        did = str(d.get('id') or (i + 1))
        name = d.get('indevice') or d.get('name') or d.get('outdevice') or ''
        names.append(did)
        labels.append(('%s: %s' % (did, name)) if name else 'Device %s' % did)
    if not names:
        names, labels = ['1'], ['1 (no device in the MIDI Device Mapper)']
    return names, labels


def refresh_devices(c):
    names, labels = device_menu(devices(c))
    p = _try(lambda: c.par['Device'])
    if p is not None:
        cur = _try(p.eval, '')
        p.menuNames, p.menuLabels = names, labels
        if cur in names:
            p.val = cur
    return names, labels


def monitor(c, n=20):
    t = c.op('events')
    rows = _rows(t) if t is not None else []
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:][-int(n):]]


def status(c):
    try:
        ms = mappings(c)
    except Exception as e:  # a hand-edited bindings row that does not parse: say so, do not fail the status
        return {'enable': enabled(c), 'active_bank': active_bank(c), 'bindings_error': '%s: %s' % (type(e).__name__, e),
                'learn': learn_status(c), 'last_events': monitor(c, 5), 'last_error': cfg(c, 'last_error')}
    k = core(c)
    bank = active_bank(c)
    live = k.select_bank(ms, bank)
    unbound = [m['id'] for m in ms if not m['target']]
    broken = [m['id'] for m in ms if m['target'] and resolve(c, m)[1] is None]
    s = state(c)
    return {'enable': enabled(c), 'feedback': feedback_on(c), 'device': _par(c, 'Device', cfg(c, 'device')),
            'active_bank': bank, 'banks': k.banks_in(ms), 'mappings': len(ms), 'live_in_bank': len(live),
            'unbound': unbound, 'broken_targets': broken, 'learn': learn_status(c), 'last_events': monitor(c, 5),
            'sent_last': s['sent'][-5:], 'writes': s['writes'], 'smoothing': sorted(s['smooth']),
            'last_error': cfg(c, 'last_error'), 'core_version': getattr(k, 'VERSION', None)}


# ================================================================== pars (par_exec) + editor

def on_par(c, name):
    try:
        if name == 'Learn':
            if cfg(c, 'learn_state') == 'listening':
                learn_stop(c)
            else:
                learn_start(c, 'hover')
        elif name == 'Activebank':
            on_bank(c)
        elif name == 'Sendfeedback':
            send_all_feedback(c)
        elif name == 'Openeditor':
            refresh_editor(c)
            w = c.op('editor_window')
            if w is not None:
                w.par.winopen.pulse()
        elif name == 'Refreshdevices':
            refresh_devices(c)
    except Exception as e:
        _error(c, 'on_par %s %s: %s' % (name, type(e).__name__, e))


def editor_rows(c):
    return mappings(c)


def editor_cell(c, row, col):
    if col < 0 or col >= len(EDITOR_COLS):
        return ''
    name = EDITOR_COLS[col]
    if row == 0:
        return name
    ms = editor_rows(c)
    if not ms:
        return 'no mappings yet: pulse Learn and move a control, or td_midi_learn / td_midi_map' if col == 1 else ''
    if row - 1 >= len(ms):
        return ''
    m = ms[row - 1]
    if name == 'msg':
        return msg_text(m)
    if name == 'target.par':
        return '%s.%s' % (m['target'], m['par']) if m['target'] else '(unbound)'
    if name == 'fb':
        return '1' if m['feedback'] else '0'
    if name == 'learn':
        return 'LRN'
    if name == 'del':
        return 'x'
    v = m.get(name)
    if isinstance(v, float):
        return '%g' % v
    return str(v)


def editor_edit(c, row, col, val):
    ms = editor_rows(c)
    if row < 1 or row - 1 >= len(ms) or EDITOR_COLS[col] not in EDITOR_EDITABLE:
        return None
    m = ms[row - 1]
    name, val = EDITOR_COLS[col], str(val).strip()
    try:
        if name == 'target.par':
            tgt, _dot, par = val.rpartition('.')
            fields = {'id': m['id'], 'target': tgt, 'par': par}
        elif name == 'fb':
            fields = {'id': m['id'], 'feedback': truthy(val)}
        elif name in ('min', 'max', 'smooth'):
            fields = {'id': m['id'], name: float(val)}
        elif name == 'bank':
            fields = {'id': m['id'], 'bank': int(float(val))}
        else:
            fields = {'id': m['id'], name: val}
        return put_mapping(c, fields)
    except Exception as e:
        _error(c, 'editor %s: %s' % (name, e))
        _try(lambda: refresh_editor(c))
        return None


SELECT_DEBOUNCE_S = 0.5   # list onSelect runs every frame of a press (31550 template); start/end are annotated
                          # Coords there, so `if end:` may be true each frame: one action per cell per press


def editor_select(c, row, col):
    ms = editor_rows(c)
    if row < 1 or row - 1 >= len(ms):
        return None
    s = state(c)
    now = time.time()
    last = s.get('sel_last')
    s['sel_last'] = (row, col, now)
    if last is not None and last[0] == row and last[1] == col and now - last[2] < SELECT_DEBOUNCE_S:
        return None  # same cell, same press (or a double click): never delete the next row too
    m = ms[row - 1]
    if EDITOR_COLS[col] == 'learn':
        return learn_start(c, 'slot', mapping_id=m['id'])
    if EDITOR_COLS[col] == 'del':
        return remove(c, [m['id']])
    return None


# zerror-style night look for the editor list (same palette as builders/zkit_logic.py THEMES['night'])
ED_BG = (0.094, 0.098, 0.114, 1.0)
ED_ROWS = ((0.106, 0.106, 0.106, 1.0), (0.150, 0.143, 0.155, 1.0))
ED_HEAD_BG = (0.0, 0.0, 0.0, 1.0)
ED_BLUE = (0.357, 0.561, 0.816, 1.0)
ED_TEXT = (0.816, 0.816, 0.816, 1.0)
ED_ACCENT = (0.91, 0.27, 0.11, 1.0)
ED_RED = (0.88, 0.25, 0.17, 1.0)
ED_FONT = 'Open Sans'
ED_LEFT = ('label',)
ED_RIGHT = ('target.par',)  # long paths: the end (op.par) is the part that says what it is


def _justify(name):
    return _try(lambda: getattr(JustifyType, name))  # noqa: F821  (TD enum, seen by DAT modules)


def editor_init_table(c, attribs):
    attribs.rowHeight = 24
    attribs.bgColor = ED_BG
    attribs.textColor = ED_TEXT
    _try(lambda: setattr(attribs, 'fontFace', ED_FONT))
    _try(lambda: setattr(attribs, 'fontSizeX', 12))


def editor_init_row(c, row, attribs):
    if row == 0:
        attribs.bgColor = ED_HEAD_BG
        attribs.textColor = ED_BLUE
    else:
        attribs.bgColor = ED_ROWS[row % 2]


def editor_init_cell(c, row, col, attribs):
    attribs.text = editor_cell(c, row, col)
    name = EDITOR_COLS[col] if 0 <= col < len(EDITOR_COLS) else ''
    if row > 0 and name in EDITOR_EDITABLE:
        attribs.editable = 2
    if row > 0 and name == 'learn':
        attribs.textColor = ED_ACCENT
    elif row > 0 and name == 'del':
        attribs.textColor = ED_RED
    j = _justify('CENTERLEFT') if name in ED_LEFT else (_justify('CENTERRIGHT') if name in ED_RIGHT else None)
    if j is not None:
        attribs.textJustify = j
        attribs.textOffsetX = 6 if name in ED_LEFT else -6


def refresh_editor(c):
    e = c.op('editor')
    if e is None:
        return
    lst = e.op('list')
    if lst is not None:
        lst.par.rows = max(2, len(editor_rows(c)) + 1)
        lst.par.cols = len(EDITOR_COLS)
        _try(lst.par.reset.pulse)
    h = e.op('header')
    if h is not None:
        ls = cfg(c, 'learn_state') or 'idle'
        h.par.text = 'jazib MIDI  |  bank %d  |  %d mappings  |  learn: %s %s' % (
            active_bank(c), len(editor_rows(c)), ls, cfg(c, 'learn_note'))
