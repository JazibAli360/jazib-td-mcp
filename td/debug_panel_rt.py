"""jazib-td debug panel runtime (Text DAT <debug COMP>/rt). Source of truth: td/debug_panel_rt.py; td_debug_panel
copies it in, so the panel keeps working in a saved .toe without the MCP.

Entry points (all take the debug COMP `c`):
  tick Execute DAT (Frame Start) -> tick(c): measures the real frame interval (wall clock between frame starts), reads
                                    Slice ops per frame from a lazy depth-first walk of Scope (time-capped at
                                    TICK_BUDGET_MS), and Refreshhz times a second runs one publish, staggered over
                                    frames (one phase per frame): fps graph table, top-10 cook ops, errors, MCP actions
                                    (log files read incrementally), then the text view (only while the window is open).
  click Panel Execute DAT         -> click(c, v): a click on the text view (v = 0..1 from the bottom) focuses that
                                    row's op in the network editor.
  builder                         -> reset(c); stats(c) -> the runtime's own cost (tick ms, mean / max) + real fps.

Cost rules (T-72: an open window costs fps that no cook time shows): no List COMPs (their per-cell Python callbacks
and re-layout on every reset cost ~10-18 fps with the window open); the view is 4 Text TOPs fed by spec tables
(x, y, text) with fixed line slots, composited once, shown as a Container's background TOP; a spec table is rewritten
only when its text changed (header at 2 Hz, the rest when the rows change); nothing is drawn while the window is
closed. Values are rounded so the rows do not churn. No findChildren, no cook(), no per-frame file reads, no full
json parse of big log lines. State lives in this module (_ST), never in op storage (T-67). Pure ASCII.
"""
import json
import os
import time

try:
    import td  # inside TouchDesigner
except ImportError:  # tests
    td = None

TICK_BUDGET_MS = 0.35
TOP_N = 10
ERR_N = 8
ACT_N = 8
STALE_FRAMES = 120        # an op that has not cooked for this many frames is not "cooking now"
LOG_EVERY_S = 2.0
LOG_TAIL_BYTES = 16384    # first read of a log: its tail
LOG_READ_CAP = 65536      # later reads: only the new bytes (more than this: skip to the tail)
LOG_KEEP = 40
GRAPH_BUCKET_S = 0.25
GRAPH_POINTS = 60         # 60 x 0.25 s = 15 s of real fps
SLOW_FACTOR = 1.5         # a frame longer than 1.5 / cookRate counts as slow (a visible hitch)

# text view geometry (pixels)
VIEW_W, VIEW_H = 440, 520
PAD_X, PAD_TOP = 6, 6
LINE_H = 15
CHARS = 61         # Menlo 12 px measured live: 7.0 px per char (evalTextSize), 61 x 7 + 6 < 440
_ST = {}


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _frame():
    return _try(lambda: int(td.absTime.frame), 0)


def _clock():
    return time.perf_counter()


# ================================================================== pure helpers

def cook_entry(prev, ms, cooks, frame, typ, rate=60.0):
    """One op read: (ms, cooks, frame of the last seen cook (None = not seen cooking yet), cooks/s, type).
    Re-reading an op that has not cooked since keeps its last change (no false 'stopped')."""
    if prev is None:
        return (ms, cooks, None, None, typ, frame)
    pms, pcooks, plast, pcps, _t, pread = prev
    if cooks > pcooks:
        since = plast if plast is not None else pread
        cps = (cooks - pcooks) * float(rate) / max(1, frame - since)
        return (ms, cooks, frame, cps, typ, frame)
    return (ms if ms else pms, cooks, plast, pcps, typ, frame)


def top_ops(cook, frame, n=TOP_N, stale=STALE_FRAMES):
    """cook: {path: cook_entry} -> rows [path, ms, cooks/s, type] of the ops that cooked lately, slowest first.
    Rounded (ms 2 places, cooks/s whole) so the rows only change when something really changed."""
    rows = []
    for p, v in cook.items():
        ms, _cooks, last, cps, typ = v[:5]
        if last is None or frame - last > stale:
            continue
        rows.append((round(ms, 2), p, cps or 0.0, typ))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return [[p, '%.2f' % ms, '%.0f' % cps, typ] for ms, p, cps, typ in rows[:n]]


def err_rows(errs, n=ERR_N):
    """errs: {path: (kind, msg)} -> rows sorted error > script > warning, then path."""
    order = {'error': 0, 'script': 1, 'warning': 2}
    items = sorted(errs.items(), key=lambda kv: (order.get(kv[1][0], 9), kv[0]))
    return [[p, k, (m.splitlines() or [''])[0][:120]] for p, (k, m) in items[:n]]


_DEC = json.JSONDecoder()


def _jstr_after(line, key):
    """The JSON string value of "key": in line, decoded alone (no parse of the whole, maybe huge, line)."""
    k = '"%s":' % key
    i = line.find(k)
    if i < 0:
        return None, -1
    j = i + len(k)
    while j < len(line) and line[j] == ' ':
        j += 1
    if j >= len(line) or line[j] != '"':
        return None, -1
    try:
        v, end = _DEC.raw_decode(line, j)
    except Exception:
        return None, -1
    return v, end


def parse_log_line(line):
    """One exec.log / calls.jsonl line -> (time, tool, what, ok) or None. exec.log 'end' rows only (start rows and
    torn lines are skipped); exec.log results can be KBs, so only the fields needed are decoded."""
    line = line.strip()
    if not line or not line.startswith('{'):
        return None
    if '"phase"' in line:  # logs/exec.log
        if '"phase":"end"' not in line.replace(' ', ''):
            return None
        t, _e = _jstr_after(line, 'time')
        code, end = _jstr_after(line, 'code')
        if t is None or code is None:
            return None
        ok = line[end:end + 16].replace(' ', '').startswith(',"ok":true')
        return (str(t), 'exec', code.strip().split('\n')[0][:80], 'ok' if ok else 'ERR')
    if '"cmd"' in line and len(line) < 4096:  # logs/calls.jsonl (call journal)
        try:
            r = json.loads(line)
        except Exception:
            return None
        if r.get('cmd') == 'exec':
            return None  # exec.log has it
        what = str(r.get('path') or r.get('args') or '')[:80]
        return (str(r.get('t', '')), str(r.get('cmd')), what, 'ok' if r.get('ok') else 'ERR')
    return None


def log_rows(lines, n=ACT_N):
    """Newest-first [time, tool, what, ok] rows from exec.log (td_exec end rows) and calls.jsonl lines."""
    out = [x for x in (parse_log_line(l) for l in lines) if x is not None]
    return act_rows(out, n)


def act_rows(parsed, n=ACT_N):
    out = sorted(parsed, key=lambda x: x[0], reverse=True)
    return [[t[11:19] if len(t) >= 19 else t, tool, what, ok] for t, tool, what, ok in out[:n]]


def read_new(path, st, tail=LOG_TAIL_BYTES, cap=LOG_READ_CAP):
    """Incremental log read. st (dict, per file) keeps the offset and a torn last line. First read = the tail; later
    reads = only the bytes added since; a shrunk file (rotated) starts again from its tail. -> complete new lines."""
    try:
        size = os.path.getsize(path)
    except Exception:
        return []
    off = st.get('off')
    if off is None or size < off or size - off > cap:
        start, skip_first = max(0, size - tail), size > tail
        st['buf'] = ''
    elif size == off:
        return []
    else:
        start, skip_first = off, False
    try:
        with open(path, 'rb') as f:
            f.seek(start)
            data = f.read(size - start).decode('utf-8', 'replace')
    except Exception:
        return []
    st['off'] = size
    data = st.get('buf', '') + data
    lines = data.split('\n')
    st['buf'] = lines.pop()  # torn (or empty) last line waits for the next read
    if skip_first and lines:
        lines = lines[1:]
    return lines


def tail_lines(path, nbytes=LOG_TAIL_BYTES):
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - nbytes))
            data = f.read().decode('utf-8', 'replace')
    except Exception:
        return []
    lines = data.split('\n')
    return lines[1:] if size > nbytes else lines


def frame_stats(intervals, rate=60.0):
    """Real frame intervals (s, wall clock between frame starts) -> fps, mean / max frame ms, slow frames."""
    v = [x for x in intervals if x > 0]
    if not v:
        return {'fps': None, 'ms': None, 'max_ms': None, 'slow': 0, 'n': 0}
    tot = sum(v)
    lim = SLOW_FACTOR / max(1.0, float(rate))
    return {'fps': len(v) / tot, 'ms': tot * 1000.0 / len(v), 'max_ms': max(v) * 1000.0,
            'slow': sum(1 for x in v if x > lim), 'n': len(v)}


def fps_text(fps, msec, dropped, tick_ms, scanned, cycle_s):
    return 'fps {} | frame {} ms | slow {} | panel {} ms'.format(
        _fmt(fps, 1), _fmt(msec, 1), _fmt(dropped, 0), _fmt(tick_ms, 2))


def scan_text(scanned, cycle_s, max_ms, scope):
    return '{} ops / {} s scan | max frame {} ms | {}'.format(scanned, _fmt(cycle_s, 1), _fmt(max_ms, 1), scope)


def _fmt(v, d):
    try:
        return ('%.' + str(d) + 'f') % float(v)
    except Exception:
        return '-'


def fit(s, n, left=False):
    """Fixed-width cell: cut to n chars ('..' marks the cut; left=True keeps the tail, for paths), pad to n."""
    s = str(s).replace('\n', ' ').replace('\t', ' ')
    if len(s) > n:
        s = ('..' + s[len(s) - n + 2:]) if left else (s[:n - 2] + '..')
    return s + ' ' * (n - len(s))


def short_path(p, scope):
    scope = (scope or '').rstrip('/')
    if scope and p.startswith(scope + '/'):
        return p[len(scope) + 1:]
    return p


def view_lines(head, top, errs, n_errs, acts, scope='', chars=CHARS):
    """-> fixed slots [(kind, text, path)], kind in head / title / body / err / '' (blank). Slots never move, so a
    click maps to a row by its line number and a changed row does not shift the others."""
    L = []

    def add(kind, text='', path=None):
        L.append((kind, text.rstrip(), path))
    add('head', head[0] if head else '')
    add('head', head[1] if len(head) > 1 else '')
    add('body', 'click a row: the network editor jumps to that op')
    w = chars - 7 - 5 - 13 - 3
    add('title', 'TOP COOKS' + ' ' * (w - 9 + 1) + fit('ms', 7) + fit('/s', 5) + 'type')
    for i in range(TOP_N):
        if i < len(top):
            p, ms, cps, typ = top[i]
            add('body', fit(short_path(p, scope), w, True) + ' ' + fit(ms, 7) + fit(cps, 5) + fit(typ, 13), p)
        else:
            add('')
    add('')
    more = n_errs - len(errs)
    add('title', 'ERRORS + WARNINGS ({}{})'.format(n_errs, ', {} more'.format(more) if more > 0 else ''))
    for i in range(ERR_N):
        if i < len(errs):
            p, k, m = errs[i]
            pw = 26
            add('err' if k in ('error', 'script') else 'body',
                fit(short_path(p, scope), pw, True) + ' ' + {'error': 'E', 'script': 'S'}.get(k, 'W') + ' ' +
                fit(m, chars - pw - 3), p)
        else:
            add('body', '  none') if (i == 0 and not errs) else add('')
    add('')
    add('title', 'RECENT MCP ACTIONS')
    for i in range(ACT_N):
        if i < len(acts):
            t, tool, what, ok = acts[i]
            p = what if what.startswith('/') else None
            add('err' if ok != 'ok' else 'body',
                fit(t, 9) + fit(tool, 9) + fit(what, chars - 9 - 9 - 4) + ' ' + ok, p)
        else:
            add('')
    return L


def spec_rows(lines, kind, h=VIEW_H, pad_x=PAD_X, pad_top=PAD_TOP, line_h=LINE_H):
    """Text TOP spec rows (x, y, text; aligny bottom, y from the bottom) for the lines of one kind."""
    rows = []
    for i, (k, text, _p) in enumerate(lines):
        if k == kind and text:
            rows.append([pad_x, h - pad_top - (i + 1) * line_h + 3, text])
    return rows


def line_at(v, n_lines, h=VIEW_H, pad_top=PAD_TOP, line_h=LINE_H):
    """Panel v (0 bottom .. 1 top) -> line index or None."""
    try:
        y = (1.0 - float(v)) * h - pad_top
    except Exception:
        return None
    if y < 0:
        return None
    i = int(y // line_h)
    return i if 0 <= i < n_lines else None


def graph_push(hist, frames, dt, points=GRAPH_POINTS):
    """One graph bucket: frames in dt seconds -> fps appended; keeps the last `points`."""
    if dt > 0:
        hist.append(round(frames / dt, 1))
    del hist[:-points]
    return hist


# ================================================================== TD side

def _state(c):
    k = c.path
    s = _ST.get(k)
    if s is None:
        s = {'gen': None, 'seen': 0, 'cycle_n': 0, 'cycle_t0': _clock(), 'cycle_s': None, 'scanned': 0,
             'cook': {}, 'errs': {}, 'last_pub': 0.0, 'last_log': 0.0, 'tick_ms': 0.0, 'tick_max': 0.0,
             'ticks': 0, 'tables': {}, 'last_t': None, 'iv': [], 'b_n': 0, 'b_t0': None, 'hist': [],
             'phase': None, 'logs': {}, 'acts_parsed': [], 'rows': {'top': [], 'errs': [], 'n_errs': 0, 'acts': []},
             'lines': [], 'writes': 0, 'renders': 0, 'pubs': 0}
        _ST[k] = s
    return s


def reset(c):
    _ST.pop(c.path, None)
    return True


def stats(c):
    s = _state(c)
    fs = frame_stats(s['iv'][-120:], _try(lambda: float(td.project.cookRate), 60.0) or 60.0)
    return {'tick_ms_mean': round(s['tick_ms'], 4), 'tick_ms_max': round(s['tick_max'], 4), 'ticks': s['ticks'],
            'ops_last_cycle': s['scanned'], 'cycle_s': s['cycle_s'],
            'real_fps_2s': None if fs['fps'] is None else round(fs['fps'], 2),
            'frame_ms_max_2s': None if fs['max_ms'] is None else round(fs['max_ms'], 1), 'slow_2s': fs['slow'],
            'graph': list(s['hist'][-8:]), 'table_writes': s['writes'], 'view_renders': s['renders'],
            'publishes': s['pubs']}


def _walk(scope, skip):
    """Lazy pre-order walk (no findChildren): yields ops, never the debug COMP, /jazib_mcp or their insides."""
    stack = [scope]
    while stack:
        o = stack.pop()
        kids = _try(lambda: list(o.children), []) or []
        for ch in reversed(kids):
            p = _try(lambda: ch.path, '')
            if not p or any(p == s_ or p.startswith(s_ + '/') for s_ in skip):
                continue
            yield ch
            if _try(lambda: ch.isCOMP, False) and not _try(lambda: ch.par.clone.eval() not in (None, ch), False):
                stack.append(ch)


def _par(c, name, default):
    v = _try(lambda: getattr(c.par, name).eval(), None)
    return default if v is None or v == '' else v


def _measure(s, t0):
    last = s['last_t']
    s['last_t'] = t0
    if last is None:
        s['b_t0'] = t0
        return
    dt = t0 - last
    if dt > 2.0:  # the panel was off / TD was busy for long: start the measure again
        s['iv'] = []
        s['b_t0'], s['b_n'] = t0, 0
        return
    s['iv'].append(dt)
    if len(s['iv']) > 240:
        del s['iv'][:-120]
    s['b_n'] += 1
    if t0 - s['b_t0'] >= GRAPH_BUCKET_S:
        graph_push(s['hist'], s['b_n'], t0 - s['b_t0'])
        s['b_t0'], s['b_n'] = t0, 0


def _scan(c, s, frame, budget_ms):
    if s['gen'] is None:
        scope = _try(lambda: c.op(str(_par(c, 'Scope', '/project1')))) or _try(lambda: td.op(str(_par(c, 'Scope', '/project1'))))
        if scope is None:
            return
        s['gen'] = _walk(scope, (c.path, '/jazib_mcp'))
    n = int(_par(c, 'Slice', 30))
    rate = _try(lambda: float(td.project.cookRate), 60.0) or 60.0
    end = _clock() + budget_ms / 1000.0
    read = 0
    while read < n and _clock() < end:
        try:
            o = next(s['gen'])
        except StopIteration:
            s['gen'] = None
            s['scanned'] = s['cycle_n']
            s['cycle_s'] = _clock() - s['cycle_t0']
            s['cycle_n'] = 0
            s['cycle_t0'] = _clock()
            # ops gone from the project leave the tables
            alive = s.get('alive')
            if alive is not None:
                for d in [p for p in s['cook'] if p not in alive]:
                    s['cook'].pop(d, None)
                    s['errs'].pop(d, None)
            s['alive'] = set()
            break
        except Exception:
            s['gen'] = None
            break
        read += 1
        s['cycle_n'] += 1
        p = _try(lambda: o.path)
        if p is None:
            continue
        if s.get('alive') is not None:
            s['alive'].add(p)
        ms = _try(lambda: float(o.cpuCookTime), 0.0) + _try(lambda: float(o.gpuCookTime), 0.0)
        cooks = _try(lambda: int(o.totalCooks), 0)
        s['cook'][p] = cook_entry(s['cook'].get(p), ms, cooks, frame, _try(lambda: o.OPType, ''), rate)
        e = _try(lambda: o.errors(), '') or ''
        se = '' if e else (_try(lambda: o.scriptErrors(), '') or '')
        w = '' if (e or se) else (_try(lambda: o.warnings(), '') or '')
        if e:
            s['errs'][p] = ('error', e)
        elif se:
            s['errs'][p] = ('script', se)
        elif w:
            s['errs'][p] = ('warning', w)
        else:
            s['errs'].pop(p, None)


def tick(c):
    t0 = _clock()
    s = _state(c)
    _measure(s, t0)
    frame = _frame()
    did = False
    if s['phase'] is not None:
        _publish_step(c, s, frame, t0)
        did = True
    elif t0 - s['last_pub'] >= 1.0 / max(0.5, float(_par(c, 'Refreshhz', 2.0))):
        s['last_pub'] = t0
        s['phase'] = 0
        s['pubs'] += 1
        _publish_step(c, s, frame, t0)
        did = True
    # a publish frame scans with what is left of the budget (stagger: never both in full on one frame)
    left = TICK_BUDGET_MS - (_clock() - t0) * 1000.0 if did else TICK_BUDGET_MS
    if left > 0.05:
        _scan(c, s, frame, left)
    dt = (_clock() - t0) * 1000.0
    s['ticks'] += 1
    s['tick_ms'] = dt if s['ticks'] == 1 else s['tick_ms'] * 0.95 + dt * 0.05
    s['tick_max'] = max(s['tick_max'] * 0.999, dt)


def _write_table(c, name, header, rows, s):
    key = json.dumps(rows)
    if s['tables'].get(name) == key:
        return False
    t = c.op(name)
    if t is None:
        return False
    t.clear()
    t.appendRow(header)
    if rows and hasattr(t, 'appendRows'):
        t.appendRows(rows)
    else:
        for r in rows:
            t.appendRow(r)
    s['tables'][name] = key
    s['writes'] += 1
    return True


def _window_open(c):
    return bool(_try(lambda: c.op('debug_window').isOpen, False))


PHASES = ('graph', 'top', 'errs', 'acts', 'view')


def _publish_step(c, s, frame, now):
    ph = PHASES[s['phase']]
    s['phase'] = s['phase'] + 1 if s['phase'] + 1 < len(PHASES) else None
    if ph == 'graph':
        h = s['hist']
        if h:
            _write_table(c, 'fps_hist', ['fps'], [[v] for v in h], s)
    elif ph == 'top':
        rows = top_ops(s['cook'], frame)
        s['rows']['top'] = rows
        _write_table(c, 'top_ops', ['path', 'ms', 'cooks/s', 'type'], rows, s)
    elif ph == 'errs':
        rows = err_rows(s['errs'])
        s['rows']['errs'], s['rows']['n_errs'] = rows, len(s['errs'])
        _write_table(c, 'errs', ['path', 'kind', 'message'], rows, s)
    elif ph == 'acts':
        if now - s['last_log'] >= LOG_EVERY_S:
            s['last_log'] = now
            d = str(_par(c, 'Logdir', ''))
            new = []
            for f in ('exec.log', 'calls.jsonl'):
                st = s['logs'].setdefault(f, {})
                new += [x for x in (parse_log_line(l) for l in read_new(os.path.join(d, f), st)) if x is not None]
            if new:
                s['acts_parsed'] = sorted(s['acts_parsed'] + new, key=lambda x: x[0])[-LOG_KEEP:]
            rows = act_rows(s['acts_parsed'])
            s['rows']['acts'] = rows
            _write_table(c, 'acts', ['time', 'tool', 'what', 'ok'], rows, s)
    elif ph == 'view':
        if not _window_open(c):
            return  # nothing is drawn while the window is closed (tables above stay current for agents)
        _render(c, s)


def _render(c, s):
    rate = _try(lambda: float(td.project.cookRate), 60.0) or 60.0
    fs = frame_stats(s['iv'][-60:], rate)
    r = s['rows']
    head = [fps_text(fs['fps'], fs['ms'], fs['slow'], s['tick_ms'], s['scanned'] or s['cycle_n'], s['cycle_s']),
            scan_text(s['scanned'] or s['cycle_n'], s['cycle_s'], fs['max_ms'], str(_par(c, 'Scope', '/project1')))]
    lines = view_lines(head, r['top'], r['errs'], r['n_errs'], r['acts'], str(_par(c, 'Scope', '/project1')))
    s['lines'] = lines
    for kind in ('head', 'title', 'body', 'err'):
        rows = spec_rows(lines, kind)
        if _write_table(c, 'sp_' + kind, ['x', 'y', 'text'], rows, s):
            s['renders'] += 1


def click(c, v):
    """A left click on the text view: focus the op of that row (top cooks, errors, actions that name an op)."""
    s = _state(c)
    i = line_at(v, len(s['lines']))
    if i is None:
        return False
    p = s['lines'][i][2]
    return focus(c, p) if p else False


def focus(c, path):
    """Network editor -> the op (the MCP's own focus helper when /jazib_mcp is loaded, else the same steps here)."""
    if not path or not str(path).startswith('/'):
        return False
    h = _try(lambda: td.op('/jazib_mcp/handlers').module)
    if h is not None and hasattr(h, 'cmd_focus'):
        if _try(lambda: h.cmd_focus(str(path)), None) is not None:
            return True
    o = _try(lambda: td.op(str(path)))
    if o is None:
        return False
    owner = _try(lambda: o.parent()) or o
    panes = _try(lambda: list(td.ui.panes), []) or []
    pane = _try(lambda: td.ui.panes.current)
    if pane is None or 'NETWORK' not in str(_try(lambda: pane.type, '')).upper():
        pane = next((p for p in panes if 'NETWORK' in str(_try(lambda: p.type, '')).upper()), None)
    for x in _try(lambda: list(owner.selectedChildren), []) or []:
        _try(lambda: setattr(x, 'selected', False))
    _try(lambda: setattr(o, 'current', True))
    _try(lambda: setattr(o, 'selected', True))
    if pane is not None:
        _try(lambda: setattr(pane, 'owner', owner))
        _try(lambda: pane.homeSelected(zoom=False))
    return True
