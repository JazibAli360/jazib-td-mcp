"""Jazib MCP for TouchDesigner -- crash fingerprints (pure Python, stdlib only, no TD calls).

Two users:
  * td/handlers.py (inside TD): cmd_exec asks check(code, patterns, frames, context) before it runs any td_exec code.
    A pattern whose code features match and whose action is "refuse" blocks the call unless the code carries the
    pattern's opt-out marker (e.g. "# allow-readback") or frames >= the pattern's frames_ok. handlers loads this file
    the way it loads td/debug.py (read from beside handlers.py, exec'd into its own module, re-read on mtime change).
  * td_crash_report (src/crash.js, TD not needed):
        python3 -I td/crashdb.py report [--ips FILE] [--diag-dir DIR] [--exec-log F] [--fh-log F] [--patterns F]
    parses the newest ~/Library/Logs/DiagnosticReports/TouchDesigner-*.ips (JSON), the faulthandler log tail
    (logs/td_faulthandler.log, written by handlers.install_faulthandler) and the td_execs in flight (logs/exec.log)
    and prints one JSON summary with known-pattern matches and a PROPOSED new pattern (never added automatically).

Pattern data: logs/crash_patterns.json {"version": 1, "patterns": [...]}. One pattern:
  id, learnings (LEARNINGS id, e.g. "T-74"), title, description, rule,
  matcher {all: [term], any: [term], none: [term]}  -- term = a code feature glob ("call:numpyArray",
          "assign:par.font*", "kw:cook.force") or "re:<regex>" (searched in the code with comments removed);
          every `all` term must hit, at least one `any` term (when given), no `none` term
  when {open_windows: true}  -- only when a Window COMP is open (handlers passes context)
  action "refuse" | "warn", optout "# allow-xxx" (null = none), frames_ok (int or null = frames do not help),
  stack {signals: ["SIGSEGV"], top: ["libGX", "libC_TOP"], contains: ["libC_DAT"], thread: "main"|"non-main"},
  reports [.ips file names], status ("seed" | "proposed" | "active").
Code features: call:<name> (function or method name), kw:<call>.<keyword> (keyword not False/None/0),
assign:<last attr> and assign:par.<parname> for assignments (also setattr and op.par['name']).

ASCII only (td-port LEARNINGS rule 1).
"""
import ast
import datetime
import fnmatch
import glob
import io
import json
import os
import re
import sys
import tokenize

VERSION = 1
FH_HEADER_RE = re.compile(r'^=== jazib-td faulthandler session (.*?) ===\s*$')
FH_THREAD_RE = re.compile(r'^(Current thread|Thread) (0x[0-9a-fA-F]+)')
FH_FRAME_RE = re.compile(r'^\s+File "(.*)", line (\d+) in (.*)$')
EXEC_FILE = '<jazib_mcp exec>'
SKIP_LIBS = ('libsystem_platform', 'libsystem_pthread')
ACTIONS = ('refuse', 'warn')
STOP_CALLS = frozenset((
    'op', 'ops', 'print', 'len', 'range', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'getattr',
    'hasattr', 'isinstance', 'format', 'append', 'extend', 'get', 'join', 'items', 'keys', 'values', 'split', 'strip',
    'open', 'read', 'min', 'max', 'round', 'sorted', 'enumerate', 'zip', 'abs', 'sum', 'repr', 'eval', 'exec',
    'globals', 'dict', 'update', 'pop', 'startswith', 'endswith', 'replace', 'lower', 'upper', 'any', 'all', 'type',
    'findChildren', 'parent', 'eval', 'pulse', 'store', 'fetch', 'add', 'sleep', 'time', 'dumps', 'loads'))

# Used when logs/crash_patterns.json is missing or broken: the T-74/T-76 readback guard that lived in handlers.py.
READBACK_CHANGES = ['call:create', 'kw:cook.force', 'assign:par.font*', 'assign:par.text', 'assign:par.*resolution*',
                    'assign:par.*format']
FALLBACK = [{'id': 'T-74-fallback', 'learnings': 'T-74', 'title': 'numpyArray in the script that changes TOPs',
             'description': 'fallback (crash_patterns.json unreadable)', 'matcher': {'all': ['call:numpyArray'],
                                                                                     'any': READBACK_CHANGES},
             'rule': 'change the TOP in one td_exec, read it in a second one (frames >= 2)',
             'action': 'refuse', 'optout': '# allow-readback', 'frames_ok': 2, 'stack': {}, 'status': 'fallback'},
            {'id': 'T-76-fallback', 'learnings': 'T-76', 'title': 'evalTextSize in the script that changes TOPs',
             'description': 'fallback (crash_patterns.json unreadable)', 'matcher': {'all': ['call:evalTextSize'],
                                                                                     'any': READBACK_CHANGES},
             'rule': 'create/configure the Text TOP in one td_exec, measure in a second one (frames >= 2)',
             'action': 'refuse', 'optout': '# allow-readback', 'frames_ok': 2, 'stack': {}, 'status': 'fallback'}]


# ================================================================== code features

def _chain(node):
    """Attribute / subscript names from the outside in, reversed to read left to right: t.par.font -> [par, font]."""
    out = []
    while True:
        if isinstance(node, ast.Attribute):
            out.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Subscript):
            s = node.slice
            out.append(s.value if isinstance(s, ast.Constant) and isinstance(s.value, str) else '*')
            node = node.value
        else:
            break
    return out[::-1]


def _assign_tokens(chain):
    if not chain:
        return set()
    toks = {'assign:' + chain[-1]}
    if 'par' in chain:
        i = len(chain) - 1 - chain[::-1].index('par')
        if i + 1 < len(chain):
            toks.add('assign:par.' + chain[i + 1])
    return toks


def _targets(t):
    if isinstance(t, (ast.Tuple, ast.List)):
        for e in t.elts:
            for x in _targets(e):
                yield x
    elif isinstance(t, ast.Starred):
        for x in _targets(t.value):
            yield x
    else:
        yield t


def _call_name(f):
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _falsy_const(v):
    return isinstance(v, ast.Constant) and v.value in (False, None, 0)


RX_CALL = re.compile(r'(?:\.|\b)([A-Za-z_]\w*)\s*\(')
RX_KW = re.compile(r'\b([A-Za-z_]\w*)\s*\(([^()]*)\)')
RX_KWARG = re.compile(r'\b([A-Za-z_]\w*)\s*=(?!=)\s*([^,)]*)')
RX_PAR_ASSIGN = re.compile(r"\.par(?:\.([A-Za-z_]\w*)|\[\s*['\"](\w+)['\"]\s*\])(?:\.val)?\s*(?<![=!<>])=(?!=)")
RX_ATTR_ASSIGN = re.compile(r'\.([A-Za-z_]\w*)\s*(?<![=!<>])=(?!=)')


def _regex_features(code):
    f = set('call:' + m for m in RX_CALL.findall(code))
    for name, args in RX_KW.findall(code):
        for k, v in RX_KWARG.findall(args):
            if v.strip() not in ('False', 'None', '0'):
                f.add('kw:{}.{}'.format(name, k))
    for a, b in RX_PAR_ASSIGN.findall(code):
        f.add('assign:par.' + (a or b))
    for a in RX_ATTR_ASSIGN.findall(code):
        f.add('assign:' + a)
    return f


def features(code):
    """(set of feature tokens, parsed_ok). Unparseable code falls back to regex approximations."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return _regex_features(code), False
    f = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = _call_name(n.func)
            if not name:
                continue
            f.add('call:' + name)
            for kw in n.keywords:
                if kw.arg and not _falsy_const(kw.value):
                    f.add('kw:{}.{}'.format(name, kw.arg))
            if name == 'setattr' and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) \
                    and isinstance(n.args[1].value, str):
                f |= _assign_tokens(_chain(n.args[0]) + [n.args[1].value])
        elif isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for el in _targets(t):
                    f |= _assign_tokens(_chain(el))
    return f, True


def strip_comments(code):
    """Code without # comments (strings kept); best effort on code that does not tokenize."""
    try:
        toks = [t for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type != tokenize.COMMENT]
        return tokenize.untokenize(toks)
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return '\n'.join(re.sub(r'(^|\s)#.*$', r'\1', ln) for ln in code.split('\n'))


def term_hits(term, code_nc, feats):
    """Evidence a term hits: [] (no hit), ['re:...'] or the matching feature tokens."""
    if not isinstance(term, str) or not term:
        return []
    if term.startswith('re:'):
        try:
            return [term] if re.search(term[3:], code_nc) else []
        except re.error:
            return []
    return sorted(x for x in feats if fnmatch.fnmatchcase(x, term))


def _dedupe(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def match_code(pattern, code_nc, feats):
    """Hits of a pattern's matcher ([] = no match)."""
    m = pattern.get('matcher') or {}
    alls, anys, nones = m.get('all') or [], m.get('any') or [], m.get('none') or []
    if not alls and not anys:
        return []
    hits = []
    for t in alls:
        h = term_hits(t, code_nc, feats)
        if not h:
            return []
        hits += h
    if anys:
        ah = [x for t in anys for x in term_hits(t, code_nc, feats)]
        if not ah:
            return []
        hits += ah
    if any(term_hits(t, code_nc, feats) for t in nones):
        return []
    return _dedupe(hits)


def check(code, patterns, frames=0, context=None):
    """Patterns this td_exec code matches: [{id, learnings, title, rule, action, hits, blocked, allowed_by, optout,
    frames_ok, unknown}]. blocked = refuse and neither opted out nor late enough. context: {'open_windows': [...]};
    a `when` key missing from context is listed in `unknown` and treated as true."""
    if not isinstance(code, str):
        return []
    feats, _ok = features(code)
    code_nc = strip_comments(code)
    out = []
    for p in patterns or []:
        if not isinstance(p, dict) or p.get('status') == 'proposed':
            continue
        hits = match_code(p, code_nc, feats)
        if not hits:
            continue
        unknown = []
        when = p.get('when') or {}
        if when.get('open_windows'):
            if context is None or 'open_windows' not in context:
                unknown.append('open_windows')
            elif not context['open_windows']:
                continue
        optout = p.get('optout')
        fo = p.get('frames_ok')
        allowed_by = None
        if optout and optout in code:
            allowed_by = 'optout'
        elif fo is not None and int(frames or 0) >= int(fo):
            allowed_by = 'frames>={}'.format(int(fo))
        action = p.get('action', 'refuse')
        out.append({'id': p.get('id'), 'learnings': p.get('learnings'), 'title': p.get('title'), 'rule': p.get('rule'),
                    'action': action, 'hits': hits, 'blocked': action == 'refuse' and allowed_by is None,
                    'allowed_by': allowed_by, 'optout': optout, 'frames_ok': fo, 'unknown': unknown,
                    'everywhere': bool(p.get('everywhere')), 'only': list(p.get('only') or [])})
    return out


def _how_to_pass(m):
    ways = []
    if m.get('frames_ok') is not None:
        ways.append('run the read in a second td_exec with frames >= {}'.format(m['frames_ok']))
    if m.get('optout'):
        ways.append('add "{}" if you are sure'.format(m['optout']))
    return ' or '.join(ways) or 'no opt-out: change the code'


def refusal_text(matches, where='logs/crash_patterns.json'):
    lines = ['crash guard: refused, this code matches a pattern that crashed TD ({}):'.format(where)]
    for m in matches:
        if not m.get('blocked'):
            continue
        lines.append('- {} {} [{}]: {} Pass: {}.'.format(m.get('learnings') or m.get('id'), m.get('title') or '',
                                                           ', '.join(m.get('hits') or [])[:200], m.get('rule') or '',
                                                           _how_to_pass(m)))
    return '\n'.join(lines)


def notes_for(matches):
    out = []
    for m in matches:
        if m.get('blocked'):
            continue
        why = 'allowed by {}'.format(m['allowed_by']) if m.get('allowed_by') else 'warn only'
        out.append('crash guard: matches {} {} ({}): {}'.format(m.get('learnings') or m.get('id'), m.get('title') or '',
                                                             why, m.get('rule') or ''))
    return out


# ================================================================== pattern file

def validate_pattern(p, proposed=False):
    """Problems with one pattern ([] = fine)."""
    probs = []
    if not isinstance(p, dict):
        return ['not an object']
    for k in ('id', 'title', 'description', 'rule'):
        if not isinstance(p.get(k), str) or not p.get(k):
            probs.append('{} missing'.format(k))
    m = p.get('matcher')
    if not isinstance(m, dict):
        probs.append('matcher missing')
    else:
        terms = []
        for k in ('all', 'any', 'none'):
            v = m.get(k, [])
            if not isinstance(v, list):
                probs.append('matcher.{} is not a list'.format(k))
                continue
            terms += v
        if not proposed and not (m.get('all') or m.get('any')):
            probs.append('matcher has no all/any terms')
        for t in terms:
            if not isinstance(t, str) or not t:
                probs.append('bad term {!r}'.format(t))
            elif t.startswith('re:'):
                try:
                    re.compile(t[3:])
                except re.error as e:
                    probs.append('bad regex {!r}: {}'.format(t, e))
            elif not re.match(r'^(call|kw|assign):', t):
                probs.append('term {!r} is not call:/kw:/assign:/re:'.format(t))
    if p.get('action', 'refuse') not in ACTIONS:
        probs.append('action must be refuse or warn')
    fo = p.get('frames_ok')
    if fo is not None and (not isinstance(fo, int) or fo < 1):
        probs.append('frames_ok must be null or an int >= 1')
    oo = p.get('optout')
    if oo is not None and (not isinstance(oo, str) or not oo.startswith('#')):
        probs.append('optout must be null or a "# ..." comment marker')
    st = p.get('stack', {})
    if not isinstance(st, dict):
        probs.append('stack must be an object')
    return probs


def load_patterns(path):
    """(patterns, error). A missing or broken file gives the FALLBACK readback guard plus the error text."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pats = data.get('patterns') if isinstance(data, dict) else None
        if not isinstance(pats, list):
            raise ValueError('no "patterns" list')
        bad = [(p.get('id') if isinstance(p, dict) else i, validate_pattern(p)) for i, p in enumerate(pats)
               if not (isinstance(p, dict) and p.get('status') == 'proposed')]
        bad = [b for b in bad if b[1]]
        if bad:
            raise ValueError('invalid patterns: {}'.format(bad[:3]))
        return pats, None
    except Exception as e:  # noqa: BLE001 -- any failure means: guard with the fallback, say why
        return [dict(p) for p in FALLBACK], '{}: {}'.format(path, e)


# ================================================================== crash reports (.ips, faulthandler, exec.log)

def ips_epoch(s):
    """'2026-10-26 15:53:36.2852 +0500' -> epoch seconds (None if unparseable)."""
    m = re.match(r'(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d):(\d\d)(?:\.(\d+))?\s*([+-])(\d\d):?(\d\d)', s or '')
    if not m:
        return None
    y, mo, d, h, mi, se = (int(m.group(i)) for i in range(1, 7))
    frac = float('0.' + m.group(7)) if m.group(7) else 0.0
    off = (int(m.group(9)) * 60 + int(m.group(10))) * (1 if m.group(8) == '+' else -1)
    tz = datetime.timezone(datetime.timedelta(minutes=off))
    return datetime.datetime(y, mo, d, h, mi, se, tzinfo=tz).timestamp() + frac


def iso_epoch(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError):
        return None


def _lib(name):
    if not name:
        return None
    return name[:-6] if name.endswith('.dylib') else name


def thread_chain(thread, images):
    """Library names of a thread's frames, innermost first, consecutive repeats collapsed, unknown images and
    libsystem_platform (the signal trampoline) / libsystem_pthread (thread start) dropped."""
    out = []
    for fr in thread.get('frames') or []:
        i = fr.get('imageIndex')
        name = _lib(images[i].get('name')) if isinstance(i, int) and 0 <= i < len(images) else None
        if not name or name in SKIP_LIBS:
            continue
        if not out or out[-1] != name:
            out.append(name)
    return out


def parse_ips(text, file=None):
    """Summary of a macOS .ips crash report (JSON: one header line + one body object)."""
    text = text.lstrip('\ufeff')
    head, _, body = text.partition('\n')
    try:
        hdr = json.loads(head)
        d = json.loads(body) if body.strip() else hdr
    except ValueError:
        d, hdr = json.loads(text), {}
    images = d.get('usedImages') or []
    threads = d.get('threads') or []
    ft = d.get('faultingThread')
    if not isinstance(ft, int):
        ft = next((i for i, t in enumerate(threads) if t.get('triggered')), None)
    th = threads[ft] if isinstance(ft, int) and 0 <= ft < len(threads) else {}
    chain = thread_chain(th, images)
    syms = []
    for fr in (th.get('frames') or [])[:24]:
        if fr.get('symbol') and fr['symbol'] not in syms:
            syms.append(fr['symbol'])
    exc = d.get('exception') or {}
    t = d.get('captureTime') or hdr.get('timestamp')
    return {
        'file': os.path.basename(file) if file else None,
        'app': hdr.get('app_name') or d.get('procName'),
        'app_version': hdr.get('app_version') or (d.get('bundleInfo') or {}).get('CFBundleShortVersionString'),
        'os': hdr.get('os_version'),
        'time': t, 'epoch': ips_epoch(t), 'launched': d.get('procLaunch'), 'launch_epoch': ips_epoch(d.get('procLaunch')),
        'pid': d.get('pid'), 'translated': d.get('translated'), 'cpu': d.get('cpuType'),
        'exception': {'type': exc.get('type'), 'signal': exc.get('signal'), 'subtype': exc.get('subtype')},
        'termination': d.get('termination'),
        'faulting_thread': {'index': ft, 'name': th.get('name'), 'queue': th.get('queue'), 'main': ft == 0},
        'chain': chain, 'top': chain[:6],
        'python_in_stack': 'Python' in chain,
        'symbols': syms[:12],
        'main_thread_top': thread_chain(threads[0], images)[:5] if threads else [],
        'threads': len(threads),
    }


def stack_matches(summary, pattern):
    st = pattern.get('stack') or {}
    if not st or not (st.get('top') or st.get('contains') or st.get('signals')):
        return False
    chain = summary.get('chain') or []
    sig = (summary.get('exception') or {}).get('signal')
    if st.get('signals') and sig not in st['signals']:
        return False
    top = st.get('top') or []
    if chain[:len(top)] != list(top):
        return False
    if any(x not in chain for x in st.get('contains') or []):
        return False
    th = st.get('thread')
    main = (summary.get('faulting_thread') or {}).get('main')
    if th == 'main' and not main or th == 'non-main' and main:
        return False
    return True


def newest_ips(diag_dir, prefix='TouchDesigner'):
    files = glob.glob(os.path.join(diag_dir, prefix + '*.ips'))
    return max(files, key=os.path.getmtime) if files else None


def parse_fh_log(text, pid=None, tail=60):
    """The faulthandler session of `pid` (else the newest): header fields, whether it holds a fatal error, the
    Python stacks per thread and the last `tail` lines."""
    lines = text.splitlines()
    sessions = []
    for i, ln in enumerate(lines):
        m = FH_HEADER_RE.match(ln)
        if m:
            kv = dict(x.split('=', 1) for x in m.group(1).split() if '=' in x)
            sessions.append((i, kv))
    if not sessions:
        return {'session': None, 'sessions': 0, 'crashed': False, 'note': 'no session header in the log'}
    pick = None
    if pid is not None:
        cand = [s for s in sessions if s[1].get('pid') == str(pid)]
        pick = cand[-1] if cand else None
    if pick is None:
        if pid is not None:
            return {'session': None, 'sessions': len(sessions), 'crashed': False,
                    'note': 'no faulthandler session for pid {} (TD crashed before the handlers loaded it, or the '
                            'log was rotated)'.format(pid)}
        pick = sessions[-1]
    start = pick[0]
    nxt = [s[0] for s in sessions if s[0] > start]
    block = lines[start:(nxt[0] if nxt else len(lines))]
    fatal = [ln for ln in block if ln.startswith('Fatal Python error')]
    threads, cur = [], None
    for ln in block:
        m = FH_THREAD_RE.match(ln)
        if m:
            cur = {'id': m.group(2), 'current': m.group(1) == 'Current thread', 'frames': []}
            threads.append(cur)
            continue
        f = FH_FRAME_RE.match(ln)
        if f and cur is not None and len(cur['frames']) < 30:
            cur['frames'].append({'file': f.group(1), 'line': int(f.group(2)), 'func': f.group(3)})
    exec_frames = [dict(fr, thread=t['id']) for t in threads for fr in t['frames'] if fr['file'] == EXEC_FILE]
    return {'session': pick[1], 'sessions': len(sessions), 'crashed': bool(fatal), 'fatal': fatal[:4],
            'threads': threads[:16], 'exec_frames': exec_frames[:10], 'tail': block[-max(1, int(tail)):]}


def _exec_rows(lines):
    rows = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get('phase') in ('start', 'end'):
            r['_t'] = iso_epoch(r.get('time'))
            if r['_t'] is not None:
                rows.append(r)
    return rows


def _clip(s, n):
    s = s if isinstance(s, str) else json.dumps(s)
    return s if s is None or len(s) <= n else s[:n] + '...'


def exec_pairs(lines):
    """exec.log rows -> [{start, end|None}] paired by (pid, code), first in first out."""
    open_, out = {}, []
    for r in _exec_rows(lines):
        key = (r.get('pid'), r.get('code'))
        if r['phase'] == 'start':
            e = {'start': r, 'end': None}
            open_.setdefault(key, []).append(e)
            out.append(e)
        else:
            q = open_.get(key)
            if q:
                q.pop(0)['end'] = r
    return out


DEAD_RE = re.compile(r'TouchDesigner (timeout|disconnected)|not connected|ECONNREFUSED|fetch failed|aborted', re.I)
HUNG_GAP_S = 30.0  # report written this long after TD's last reply: TD sat hung on its crash dialog first (T-76)


def _iso(t):
    if t is None:
        return None
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def exec_in_flight(lines, crash_epoch=None, window_s=120, recent_s=20, code_chars=600, launch_epoch=None):
    """td_execs in flight when TD died. An exec is dead when it never ended or ended with a bridge timeout /
    disconnect; any other end is a reply (TD was alive then). The crash time is estimated as the report time, or
    TD's last reply before it when the report came > HUNG_GAP_S later (TD hung on its crash dialog, T-76). in_flight
    = dead execs started in [estimate - window_s, estimate + HUNG_GAP_S] (and after TD launched); recent = execs that
    replied in the recent_s before the estimate (newest 5); later_dead = dead execs started after that (victims)."""
    pairs = exec_pairs(lines)
    if not pairs:
        return {'in_flight': [], 'codes': [], 'recent': [], 'later_dead': 0, 'crash_estimate': _iso(crash_epoch),
                'basis': 'no exec.log rows', 'last_reply': None}

    def dead(p):
        e = p['end']
        return e is None or (e.get('ok') is False and bool(DEAD_RE.search(str(e.get('error') or ''))))

    lo = launch_epoch if launch_epoch is not None else float('-inf')
    hi = crash_epoch
    if hi is None:
        hi = max(p['start']['_t'] if p['end'] is None else p['end']['_t'] for p in pairs)
    replies = [p['end']['_t'] for p in pairs if not dead(p) and lo <= p['end']['_t'] <= hi + 2]
    last_reply = max(replies) if replies else None
    est, basis = hi, ('crash report time' if crash_epoch is not None else 'end of exec.log')
    if crash_epoch is not None and last_reply is not None and hi - last_reply > HUNG_GAP_S:
        est = last_reply
        basis = ('TD\'s last td_exec reply (report written {:.0f} s later: TD hung on its crash dialog, or no td_exec '
                 'ran in between)'.format(hi - last_reply))
    fl, rec, later = [], [], 0
    for p in pairs:
        s, e = p['start'], p['end']
        if dead(p):
            if s['_t'] < lo:
                continue
            if est - window_s <= s['_t'] <= est + HUNG_GAP_S:
                row = {'time': s.get('time'), 'before_crash_s': round(est - s['_t'], 1), 'pid': s.get('pid'),
                       'agent': s.get('agent'), 'code': _clip(s.get('code') or '', code_chars)}
                if e is not None:
                    row['ended'] = {'time': e.get('time'), 'error': _clip(e.get('error') or '', 200)}
                fl.append((s['_t'], row, s.get('code') or ''))
            elif est + HUNG_GAP_S < s['_t'] <= hi + 2:
                later += 1
        elif est - recent_s <= e['_t'] <= est + 0.001:
            rec.append((e['_t'], {'time': s.get('time'), 'ended': e.get('time'), 'ok': e.get('ok'), 'pid': s.get('pid'),
                                  'agent': s.get('agent'), 'code': _clip(s.get('code') or '', 200)}))
    fl.sort(key=lambda x: x[0])
    rec.sort(key=lambda x: x[0])
    return {'in_flight': [r for _t, r, _c in fl], 'codes': [c for _t, _r, c in fl], 'recent': [r for _t, r in rec[-5:]],
            'later_dead': later, 'crash_estimate': _iso(est), 'basis': basis, 'last_reply': _iso(last_reply)}


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')[:40] or 'new'


def propose_pattern(summary, codes, existing_ids=(), fh=None):
    """A NEW pattern entry for the main session to review (status "proposed"; never added automatically): stack from
    the .ips, candidate code features from the in-flight execs (generic calls dropped)."""
    sig = (summary or {}).get('exception', {}).get('signal') if summary else None
    chain = (summary or {}).get('chain') or []
    when = (summary or {}).get('time') or ''
    stamp = re.sub(r'\D', '', when)[:14] or 'unknown'
    pid_ = 'P-{}'.format(stamp)
    n = 2
    while pid_ in existing_ids:
        pid_ = 'P-{}-{}'.format(stamp, n)
        n += 1
    cand, seen = [], set()
    for c in codes or []:
        feats, _ok = features(c)
        for t in sorted(feats):
            kind, _, name = t.partition(':')
            base = name.split('.')[0]
            if kind == 'call' and base in STOP_CALLS:
                continue
            if kind == 'kw' and base in STOP_CALLS:
                continue
            if t not in seen:
                seen.add(t)
                cand.append(t)
    cand = [t for t in cand if not (t.startswith('assign:') and 'assign:par.' + t[7:] in seen)]
    thread = (summary or {}).get('faulting_thread') or {}
    fh_exec = [fr for fr in (fh or {}).get('exec_frames') or []]
    desc = '{} {} on the {} thread "{}": {}'.format(
        (summary or {}).get('exception', {}).get('type') or '?', sig or '?',
        'main' if thread.get('main') else 'non-main', thread.get('name') or '?', ' -> '.join(chain[:6]) or '?')
    if fh_exec:
        desc += '; faulthandler: td_exec line {} in {}'.format(fh_exec[0]['line'], fh_exec[0]['func'])
    return {
        'id': pid_, 'learnings': 'T-??', 'status': 'proposed',
        'title': 'TODO name the trigger ({} in {})'.format(sig or '?', '/'.join(chain[:2]) or '?'),
        'description': desc,
        'rule': 'TODO: the rule (what not to do, what to do instead)',
        'matcher': {'all': [], 'any': cand[:12], 'none': []},
        'when': {},
        'action': 'refuse', 'optout': '# allow-{}'.format(_slug(pid_)), 'frames_ok': None,
        'stack': {'signals': [sig] if sig else [], 'top': chain[:3], 'contains': [],
                  'thread': 'main' if thread.get('main') else 'non-main'},
        'reports': [summary['file']] if summary and summary.get('file') else [],
        'review': 'narrow matcher.any to the real trigger (move the must-have terms to all), set learnings/title/'
                  'rule, set status "active", then add it to logs/crash_patterns.json and LEARNINGS.md',
    }


def _read(path, limit=None):
    """Text of a file; with limit only its last `limit` bytes (a cut first line is dropped)."""
    with open(path, 'rb') as f:
        cut = False
        if limit:
            f.seek(0, 2)
            size = f.tell()
            cut = size > limit
            f.seek(max(0, size - limit))
        t = f.read().decode('utf-8', 'replace')
    return t.split('\n', 1)[1] if cut and '\n' in t else t


def report(ips=None, diag_dir=None, exec_log=None, fh_log=None, patterns_path=None, window_s=120, tail=60):
    """The td_crash_report summary (file reads only)."""
    out = {'notes': []}
    pats, perr = load_patterns(patterns_path) if patterns_path else ([], 'no patterns file given')
    if perr:
        out['notes'].append('patterns: ' + perr)
    if ips is None and diag_dir:
        ips = newest_ips(diag_dir)
    summary = None
    if ips:
        try:
            summary = parse_ips(_read(ips), ips)
            summary['path'] = ips
        except Exception as e:  # noqa: BLE001
            out['notes'].append('could not parse {}: {}'.format(ips, e))
    else:
        out['notes'].append('no TouchDesigner-*.ips in {}'.format(diag_dir))
    out['crash'] = summary
    crash_t = summary.get('epoch') if summary else None
    fh = None
    if fh_log and os.path.isfile(fh_log):
        fh = parse_fh_log(_read(fh_log, 4 * 1024 * 1024), summary.get('pid') if summary else None, tail)
    elif fh_log:
        out['notes'].append('no faulthandler log at {} (installed by handlers on load; td_reload)'.format(fh_log))
    out['faulthandler'] = fh
    codes = []
    if exec_log and os.path.isfile(exec_log):
        ex = exec_in_flight(_read(exec_log, 8 * 1024 * 1024).splitlines(), crash_t, window_s,
                            launch_epoch=summary.get('launch_epoch') if summary else None)
        codes = ex.pop('codes', [])
        out['exec'] = ex
    else:
        out['exec'] = {'in_flight': [], 'recent': []}
        out['notes'].append('no exec.log at {}'.format(exec_log))
    by_stack = [p.get('id') for p in pats if summary and stack_matches(summary, p)]
    by_code = []
    for i, c in enumerate(codes):
        for m in check(c, pats, 0, None):
            by_code.append({'exec': i, 'id': m['id'], 'learnings': m['learnings'], 'hits': m['hits'],
                            'would_block': m['blocked'], 'allowed_by': m['allowed_by']})
    both = sorted(set(by_stack) & set(m['id'] for m in by_code))
    out['known'] = {'by_stack': by_stack, 'by_code': by_code, 'both': both}
    if both:
        out['verdict'] = 'known pattern {}: stack and in-flight code both match; if the guard already had it, check ' \
                         'why it ran (opt-out marker, frames)'.format(', '.join(both))
        out['proposal'] = None
    else:
        if by_stack:
            out['verdict'] = 'stack looks like {} but no in-flight td_exec matches its code features: a new trigger ' \
                             'or code run by a builder/DAT runtime; review the proposal'.format(', '.join(by_stack))
        elif summary:
            out['verdict'] = 'unknown crash: review the proposal below'
        else:
            out['verdict'] = 'no crash report found'
        out['proposal'] = propose_pattern(summary, codes, [p.get('id') for p in pats], fh) if summary or codes else None
    out['next'] = ('main session: read crash + faulthandler + exec, write LEARNINGS T-nn (evidence, cause, rule), then '
                   'add/adjust the pattern in logs/crash_patterns.json (td_exec picks it up on the next call)')
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='crashdb.py')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('report')
    r.add_argument('--ips')
    r.add_argument('--diag-dir', default=os.path.expanduser('~/Library/Logs/DiagnosticReports'))
    r.add_argument('--exec-log')
    r.add_argument('--fh-log')
    r.add_argument('--patterns')
    r.add_argument('--window', type=int, default=120)
    r.add_argument('--tail', type=int, default=60)
    c = sub.add_parser('check')
    c.add_argument('--patterns', required=True)
    c.add_argument('--frames', type=int, default=0)
    c.add_argument('file', help='file with the code (- = stdin)')
    a = ap.parse_args(argv)
    if a.cmd == 'report':
        res = report(a.ips, a.diag_dir, a.exec_log, a.fh_log, a.patterns, a.window, a.tail)
    else:
        code = sys.stdin.read() if a.file == '-' else _read(a.file)
        pats, err = load_patterns(a.patterns)
        res = {'matches': check(code, pats, a.frames, None), 'patterns_error': err}
    sys.stdout.write(json.dumps(res, indent=1, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
