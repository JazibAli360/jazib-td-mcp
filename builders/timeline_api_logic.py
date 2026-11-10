"""TL_timeline phase 4 pure logic (no td imports): the agent-ready API on show DATA.

A show is plain JSON ("tl-show" v1):
    {"format": "tl-show", "v": 1,
     "settings": {"length": 16, "fps": 30, "bpm": 120, ...},            # custom pars of the COMP (SETTINGS)
     "lanes": [{"name", "op", "par", "min", "max", "enabled", "keys": [[t, v, interp], ...]}],
     "markers": [[t, "name"], ...],
     "clips": [{"id", "track", "start", "dur", "src", "in", "speed", "fade", "proxy", "enabled"}]}
Edits are a list of ops ({"op": "add_key", ...}, see OPS) applied to a copy of the show; atomic by default (one
bad op = nothing changes). Times may be seconds or strings: "12.5", "12.5s", "90f" (frames), "8b" (beats),
"2bar" (bars), "3.2.1" (bar.beat.16th, 1-based position), "00:00:04:15" (SMPTE), "01:04.5" (min:sec),
"@Drop" (marker), "@Drop+2b" / "@Drop-4f" (marker + offset).
The COMP's `TimelineExt` (builders/timeline_ext.py) reads its tables into a show, calls apply_ops and writes back
only the tables that changed. bind(tl_logic, clips_logic) first: key / clip maths are theirs (one source of truth).
Tested offline by test/test_timeline_api.py. Pure ASCII.
"""
import copy
import math
import re

FORMAT = 'tl-show'
VERSION = 1
TL = None   # builders/timeline_logic.py module (bind)
CL = None   # builders/timeline_clips_logic.py module (bind; None = no clips track)

LANE_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
CLIP_ID_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]{0,39}$')
MARKER_NAME_MAX = 80
MAX_OPS = 2000
MAX_KEYS = 4096
KEY_TOL = 1e-3          # default time tolerance when an op finds a key / marker by time
LANE_FIELDS = ('name', 'op', 'par', 'min', 'max', 'enabled')
CLIP_FIELDS = ('id', 'track', 'start', 'dur', 'src', 'in', 'speed', 'fade', 'proxy', 'enabled')
PARTS = ('settings', 'lanes', 'markers', 'clips')

# setting key -> (custom par, kind, allowed menu values or (min, max))
SETTINGS = {
    'length': ('Length', 'float', (0.01, None)),
    'fps': ('Fps', 'float', (1.0, 240.0)),
    'bpm': ('Bpm', 'float', (0.0, 999.0)),
    'beatsperbar': ('Beatsperbar', 'int', (1, 64)),
    'inpoint': ('Inpoint', 'float', (0.0, None)),
    'outpoint': ('Outpoint', 'float', (0.0, None)),
    'loop': ('Loop', 'bool', None),
    'rate': ('Rate', 'float', (-4.0, 4.0)),
    'snap': ('Snap', 'bool', None),
    'snapdiv': ('Snapdiv', 'int', (1, 64)),
    'snapunit': ('Snapunit', 'menu', ('beat', 'frame')),
    'tcmode': ('Tcmode', 'menu', ('smpte', 'seconds', 'frames', 'bars')),
    'clockmode': ('Clockmode', 'menu', ('realtime', 'frame')),
    'markername': ('Markername', 'str', None),
    # phase 2 clips page (absent on a phase-1 COMP: the ext skips missing pars with a warning)
    'program': ('Program', 'menu', ('clips', 'demo')),
    'maxplayers': ('Maxplayers', 'int', (1, 4)),
    'sourcemode': ('Sourcemode', 'menu', ('full', 'proxy', 'auto')),
    'blendmode': ('Blendmode', 'menu', ('over', 'add', 'screen')),
    'premult': ('Premult', 'bool', None),
    'fit': ('Fit', 'menu', ('fit', 'fill', 'stretch')),
    'preroll': ('Preroll', 'float', (0.0, 10.0)),
}
# transport state (not part of a saved show): play / seek live on the COMP too
TRANSPORT_ACTIONS = ('play', 'pause', 'toggle', 'stop', 'seek', 'step', 'start', 'end', 'next_marker',
                     'prev_marker', 'next_key', 'prev_key')


class OpError(ValueError):
    pass


def bind(tl, cl=None):
    """Point this module at the timeline + clips logic modules (TD: the COMP's tl_logic / tl_clips_logic DATs)."""
    global TL, CL
    TL, CL = tl, cl
    return True


def _num(x):
    s = '%.6f' % float(x)
    s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _finite(x, what):
    if isinstance(x, bool):
        raise OpError('%s must be a number, got %r' % (what, x))
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise OpError('%s must be a number, got %r' % (what, x))
    if v != v or v in (float('inf'), float('-inf')):
        raise OpError('%s must be finite, got %r' % (what, x))
    return v


def _bool(x, what):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)) and x in (0, 1):
        return bool(x)
    s = str(x).strip().lower()
    if s in ('1', 'true', 'on', 'yes'):
        return True
    if s in ('0', 'false', 'off', 'no'):
        return False
    raise OpError('%s must be true/false, got %r' % (what, x))


# ---------------------------------------------------------------- time strings
class Ctx(object):
    """Musical / frame context for time strings: fps, bpm, beats per bar, markers [(t, name)], length."""

    def __init__(self, fps=30.0, bpm=120.0, bpb=4, markers=(), length=None):
        self.fps = float(fps) if fps else 30.0
        self.bpm = float(bpm)
        self.bpb = max(1, int(bpb))
        self.markers = list(markers)
        self.length = length

    @classmethod
    def of(cls, show):
        s = show.get('settings', {})
        return cls(s.get('fps', 30.0), s.get('bpm', 120.0), s.get('beatsperbar', 4),
                   [(float(m[0]), str(m[1])) for m in show.get('markers', [])], s.get('length'))


_UNIT_RE = re.compile(r'^([+-]?(?:\d+\.?\d*|\.\d+))\s*(s|sec|f|fr|frames?|b|beats?|bars?)?$', re.I)
_BBS_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')
_SMPTE_RE = re.compile(r'^(\d+):(\d{1,2}):(\d{1,2})[:;](\d{1,3})$')
_MS_RE = re.compile(r'^(\d+):(\d{1,2}(?:\.\d*)?)$')
_MARK_RE = re.compile(r'^@(.+?)(?:\s*([+-])\s*([^+-].*))?$')


def _beat_s(ctx):
    if ctx.bpm <= 0:
        raise OpError('beats/bars need bpm > 0')
    return 60.0 / ctx.bpm


def duration(x, ctx):
    """A length: number = seconds; '12f' frames; '8b' beats; '2bar' bars; '1.5s'."""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return _finite(x, 'time')
    s = str(x).strip()
    m = _UNIT_RE.match(s)
    if not m:
        raise OpError('cannot read a duration from %r (use 1.5, "1.5s", "45f", "8b", "2bar")' % (x,))
    v = float(m.group(1))
    u = (m.group(2) or 's').lower()
    if u.startswith('f'):
        return v / ctx.fps
    if u.startswith('bar'):
        return v * ctx.bpb * _beat_s(ctx)
    if u.startswith('b'):
        return v * _beat_s(ctx)
    return v


def to_seconds(x, ctx):
    """A position on the timeline (see the module doc for the forms)."""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return _finite(x, 'time')
    if x is None:
        raise OpError('time missing')
    s = str(x).strip()
    m = _MARK_RE.match(s)
    if m:
        name = m.group(1).strip()
        hits = [t for t, n in ctx.markers if n == name]
        if not hits:
            raise OpError('no marker named %r (markers: %s)' % (name, [n for _, n in ctx.markers][:20]))
        t = hits[0]
        if m.group(2):
            d = duration(m.group(3).strip(), ctx)
            t = t + d if m.group(2) == '+' else t - d
        return t
    m = _BBS_RE.match(s)
    if m:
        bar, beat, six = (int(g) for g in m.groups())
        if bar < 1 or beat < 1 or six < 1:
            raise OpError('bar.beat.16th is 1-based: %r' % s)
        return ((bar - 1) * ctx.bpb + (beat - 1) + (six - 1) / 4.0) * _beat_s(ctx)
    m = _SMPTE_RE.match(s)
    if m:
        h, mi, se, ff = (int(g) for g in m.groups())
        return h * 3600 + mi * 60 + se + ff / float(max(1, int(round(ctx.fps))))
    m = _MS_RE.match(s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    return duration(s, ctx)


# ---------------------------------------------------------------- show <-> tables
def empty_show():
    return {'format': FORMAT, 'v': VERSION, 'settings': {}, 'lanes': [], 'markers': [], 'clips': []}


def show_from_tables(settings, lanes_rows, keys_rows_by_lane, marker_rows, clip_rows=None):
    """Tables (lists of string rows, header first) -> show dict. keys_rows_by_lane: {lane name: rows}."""
    sh = empty_show()
    sh['settings'] = dict(settings or {})
    for ln in TL.parse_lanes(lanes_rows or []):
        keys = TL.parse_keys(keys_rows_by_lane.get(ln['name']) or [])
        d = dict(ln)
        d['keys'] = [[k[0], k[1], k[2]] for k in keys]
        sh['lanes'].append(d)
    sh['markers'] = [[t, n] for t, n in TL.parse_markers(marker_rows or [])]
    if CL is not None and clip_rows is not None:
        sh['clips'] = [dict((k, c[k]) for k in CLIP_FIELDS) for c in CL.parse_clips(clip_rows)]
    else:
        sh['clips'] = None  # no clips track on this COMP
    return sh


def lanes_rows(show):
    rows = [list(LANE_FIELDS)]
    for ln in show['lanes']:
        rows.append([ln['name'], ln['op'], ln['par'], _num(ln['min']), _num(ln['max']),
                     '1' if ln.get('enabled', True) else '0'])
    return rows


def keys_rows(lane):
    return TL.keys_to_rows([tuple(k) for k in lane['keys']])


def marker_rows(show):
    rows = [['time', 'name']]
    for t, n in sorted(show['markers'], key=lambda m: m[0]):
        rows.append([_num(t), n])
    return rows


def clip_rows(show):
    return CL.clips_to_rows(show['clips'] or [])


def table_texts(show):
    """{table name: rows} for every table the show writes (lane_<name> per lane)."""
    out = {'lanes': lanes_rows(show), 'markers': marker_rows(show)}
    for ln in show['lanes']:
        out['lane_' + ln['name']] = keys_rows(ln)
    if show.get('clips') is not None and CL is not None:
        out['clips'] = clip_rows(show)
    return out


def changed_tables(before, after):
    """(changed {name: rows}, removed [lane table names]) between two shows."""
    a, b = table_texts(before), table_texts(after)
    changed = dict((k, v) for k, v in b.items() if a.get(k) != v)
    removed = sorted(k for k in a if k.startswith('lane_') and k not in b)
    return changed, removed


def changed_settings(before, after):
    sb, sa = before.get('settings', {}), after.get('settings', {})
    return dict((k, v) for k, v in sa.items() if sb.get(k) != v)


# ---------------------------------------------------------------- normalising a show document (load / import)
def coerce_setting(key, val):
    if key not in SETTINGS:
        raise OpError('unknown setting %r (known: %s)' % (key, sorted(SETTINGS)))
    _, kind, lim = SETTINGS[key]
    if kind == 'bool':
        return _bool(val, key)
    if kind == 'menu':
        s = str(val).strip().lower()
        if s not in lim:
            raise OpError('%s must be one of %s, got %r' % (key, list(lim), val))
        return s
    if kind == 'str':
        return str(val)[:MARKER_NAME_MAX]
    v = _finite(val, key)
    if kind == 'int':
        if v != int(v):
            raise OpError('%s must be a whole number, got %r' % (key, val))
        v = int(v)
    lo, hi = lim
    if lo is not None and v < lo:
        raise OpError('%s must be >= %s, got %r' % (key, lo, val))
    if hi is not None and v > hi:
        raise OpError('%s must be <= %s, got %r' % (key, hi, val))
    return v


def norm_keys(keys, ctx, what='keys'):
    if not isinstance(keys, (list, tuple)):
        raise OpError('%s must be a list of [t, v, interp?] or {t, v, interp?}' % what)
    if len(keys) > MAX_KEYS:
        raise OpError('%s: at most %d keys' % (what, MAX_KEYS))
    out = []
    for k in keys:
        if isinstance(k, dict):
            t, v, i = k.get('t', k.get('time')), k.get('v', k.get('value')), k.get('interp', 'linear')
        elif isinstance(k, (list, tuple)) and len(k) in (2, 3):
            t, v, i = k[0], k[1], (k[2] if len(k) == 3 else 'linear')
        else:
            raise OpError('%s: bad key %r' % (what, k))
        i = str(i).strip().lower()
        if i not in TL.INTERPS:
            raise OpError('%s: interp must be one of %s, got %r' % (what, list(TL.INTERPS), i))
        out.append([to_seconds(t, ctx), _finite(v, 'key value'), i])
    out.sort(key=lambda k: k[0])
    for a, b in zip(out, out[1:]):
        if abs(a[0] - b[0]) <= 1e-4:
            raise OpError('%s: two keys at t=%s' % (what, _num(a[0])))
    return out


def _target(spec):
    """'op.par' or {op, par} -> (op, par). The last '.' splits: '/project1/lab/x/noise1.tx'."""
    if isinstance(spec, dict):
        return str(spec.get('op', '')).strip(), str(spec.get('par', '')).strip()
    s = str(spec or '').strip()
    if '.' not in s.rsplit('/', 1)[-1]:
        raise OpError('target must be "op.par" (e.g. "demo_noise.tx"), got %r' % (spec,))
    o, p = s.rsplit('.', 1)
    return o, p


def norm_lane(d, ctx):
    name = str(d.get('name', '')).strip()
    if not LANE_NAME_RE.match(name):
        raise OpError('lane name must match %s (it names the table lane_<name>), got %r' % (LANE_NAME_RE.pattern, name))
    o, p = d.get('op', ''), d.get('par', '')
    if d.get('target') is not None:
        o, p = _target(d['target'])
    lo = _finite(d.get('min', 0.0), 'min')
    hi = _finite(d.get('max', 1.0), 'max')
    if hi == lo:
        raise OpError('lane %s: min == max' % name)
    return {'name': name, 'op': str(o).strip(), 'par': str(p).strip(), 'min': lo, 'max': hi,
            'enabled': _bool(d.get('enabled', True), 'enabled'),
            'keys': norm_keys(d.get('keys', []), ctx, 'lane %s keys' % name)}


def norm_clip(d, ctx, existing_ids=()):
    if CL is None:
        raise OpError('this timeline has no clips track (phase 2)')
    cid = str(d.get('id', '')).strip()
    if not CLIP_ID_RE.match(cid):
        raise OpError('clip id must match %s, got %r' % (CLIP_ID_RE.pattern, cid))
    if cid in existing_ids:
        raise OpError('clip id %r exists' % cid)
    src = str(d.get('src', '')).strip()
    if not src:
        raise OpError('clip %s: src (movie file, repo-relative or absolute) missing' % cid)
    if '\t' in src or '\n' in src:
        raise OpError('clip %s: src has a tab/newline' % cid)
    dur = duration(d.get('dur'), ctx) if d.get('dur') is not None else None
    if dur is None and d.get('end') is not None:
        dur = to_seconds(d['end'], ctx) - to_seconds(d.get('start', 0.0), ctx)
    if dur is None or dur <= 0:
        raise OpError('clip %s: dur (or end) must give a length > 0' % cid)
    tr = _finite(d.get('track', 0), 'track')
    if tr < 0 or tr != int(tr):
        raise OpError('clip %s: track must be a whole number >= 0' % cid)
    start = to_seconds(d.get('start', 0.0), ctx)
    if start < 0:
        raise OpError('clip %s: start < 0' % cid)
    return {'id': cid, 'track': int(tr), 'start': start, 'dur': dur, 'src': src,
            'in': max(0.0, duration(d.get('in', 0.0), ctx)), 'speed': _finite(d.get('speed', 1.0), 'speed'),
            'fade': max(0.0, duration(d.get('fade', 0.0), ctx)), 'proxy': str(d.get('proxy', '') or ''),
            'enabled': _bool(d.get('enabled', True), 'enabled')}


def _marker_name(n):
    n = str(n if n is not None else '').strip()
    if not n or '\t' in n or '\n' in n or len(n) > MARKER_NAME_MAX:
        raise OpError('marker name must be 1..%d chars without tabs/newlines, got %r' % (MARKER_NAME_MAX, n))
    return n


def norm_show(doc, current=None):
    """A show document (load / import) -> a valid show. Parts missing from doc are taken from current (or empty).
    Raises OpError naming the first problem."""
    if not isinstance(doc, dict):
        raise OpError('show must be a JSON object')
    if doc.get('format', FORMAT) != FORMAT:
        raise OpError('format must be %r, got %r' % (FORMAT, doc.get('format')))
    if int(doc.get('v', VERSION)) > VERSION:
        raise OpError('show v%s is newer than this API (v%d)' % (doc.get('v'), VERSION))
    base = copy.deepcopy(current) if current else empty_show()
    sh = empty_show()
    st = dict(base.get('settings', {}))
    for k, v in (doc.get('settings') or {}).items():
        st[k] = coerce_setting(k, v)
    sh['settings'] = st
    # markers before everything else: lanes / clips may use "@marker" times
    ms = []
    for m in (doc['markers'] if doc.get('markers') is not None else base.get('markers', [])):
        if isinstance(m, dict):
            t, n = m.get('t', m.get('time')), m.get('name')
        elif isinstance(m, (list, tuple)) and len(m) == 2:
            t, n = m
        else:
            raise OpError('bad marker %r (use [t, name] or {t, name})' % (m,))
        ms.append([None, _marker_name(n), t])
    ctx0 = Ctx(st.get('fps', 30.0), st.get('bpm', 120.0), st.get('beatsperbar', 4), [], st.get('length'))
    for m in ms:   # markers by plain time first, then any "@other" reference
        try:
            m[0] = to_seconds(m[2], ctx0)
        except OpError:
            pass
    ctx0.markers = [(m[0], m[1]) for m in ms if m[0] is not None]
    for m in ms:
        if m[0] is None:
            m[0] = to_seconds(m[2], ctx0)
    sh['markers'] = sorted([[m[0], m[1]] for m in ms], key=lambda m: m[0])
    names = [m[1] for m in sh['markers']]
    if len(set(names)) != len(names):
        raise OpError('marker names must be unique ("@name" times use them): %s' % sorted(n for n in set(names) if names.count(n) > 1))
    ctx = Ctx(st.get('fps', 30.0), st.get('bpm', 120.0), st.get('beatsperbar', 4),
              [(m[0], m[1]) for m in sh['markers']], st.get('length'))
    seen = set()
    for d in (doc['lanes'] if doc.get('lanes') is not None else base.get('lanes', [])):
        if not isinstance(d, dict):
            raise OpError('bad lane %r' % (d,))
        ln = norm_lane(d, ctx)
        if ln['name'] in seen:
            raise OpError('two lanes named %r' % ln['name'])
        seen.add(ln['name'])
        sh['lanes'].append(ln)
    if base.get('clips') is None and not doc.get('clips'):
        sh['clips'] = None
    else:
        ids = set()
        sh['clips'] = []
        for d in (doc['clips'] if doc.get('clips') is not None else base.get('clips') or []):
            if not isinstance(d, dict):
                raise OpError('bad clip %r' % (d,))
            c = norm_clip(d, ctx, ids)
            ids.add(c['id'])
            sh['clips'].append(c)
    return sh


def merge_show(current, doc):
    """Merge: lanes / clips / markers in doc replace the same-named ones (lane name, clip id, marker name) and add
    new ones; everything else in current stays. Settings in doc are set, the others kept."""
    if not isinstance(doc, dict):
        raise OpError('show must be a JSON object')
    def mname(m):
        return m.get('name') if isinstance(m, dict) else (m[1] if isinstance(m, (list, tuple)) and len(m) == 2 else None)
    dm = list(doc.get('markers') or [])
    dl = list(doc.get('lanes') or [])
    dc = list(doc.get('clips') or [])
    m_names = set(mname(m) for m in dm)
    l_names = set(l.get('name') for l in dl if isinstance(l, dict))
    c_ids = set(c.get('id') for c in dc if isinstance(c, dict))
    full = dict(doc)
    full['markers'] = [list(m) for m in current['markers'] if m[1] not in m_names] + dm
    full['lanes'] = [l for l in current['lanes'] if l['name'] not in l_names] + dl
    if dc or current.get('clips') is not None:
        full['clips'] = [c for c in (current.get('clips') or []) if c['id'] not in c_ids] + dc
    else:
        full.pop('clips', None)
    return norm_show(full, current)


# ---------------------------------------------------------------- edit ops
def _lane(show, name):
    for ln in show['lanes']:
        if ln['name'] == name:
            return ln
    raise OpError('no lane %r (lanes: %s)' % (name, [l['name'] for l in show['lanes']]))


def _key_index(lane, d, ctx):
    keys = lane['keys']
    if d.get('index') is not None:
        i = int(_finite(d['index'], 'index'))
        if i < 0:
            i += len(keys)
        if not 0 <= i < len(keys):
            raise OpError('lane %s has no key index %s (%d keys)' % (lane['name'], d['index'], len(keys)))
        return i
    if d.get('at') is None:
        raise OpError('give at (key time) or index')
    t = to_seconds(d['at'], ctx)
    tol = _finite(d.get('tol', KEY_TOL), 'tol')
    best = TL.nearest_key([tuple(k) for k in keys], t)
    if best < 0 or abs(keys[best][0] - t) > tol:
        raise OpError('lane %s: no key within %s s of t=%s' % (lane['name'], _num(tol), _num(t)))
    return best


def _clip(show, cid):
    if show.get('clips') is None:
        raise OpError('this timeline has no clips track (phase 2)')
    for c in show['clips']:
        if c['id'] == cid:
            return c
    raise OpError('no clip %r (clips: %s)' % (cid, [c['id'] for c in show['clips']][:30]))


def _marker_index(show, d, ctx):
    ms = show['markers']
    if d.get('name') is not None and d.get('at') is None:
        hits = [i for i, m in enumerate(ms) if m[1] == d['name']]
        if not hits:
            raise OpError('no marker named %r' % d['name'])
        return hits[0]
    if d.get('at') is None:
        raise OpError('give name or at')
    t = to_seconds(d['at'], ctx)
    tol = _finite(d.get('tol', KEY_TOL), 'tol')
    for i, m in enumerate(ms):
        if abs(m[0] - t) <= tol:
            return i
    raise OpError('no marker within %s s of t=%s' % (_num(tol), _num(t)))


def _snap(t, d, show):
    if not d.get('snap'):
        return t
    s = show['settings']
    unit = 'frame' if s.get('snapunit') == 'frame' else 'beat'
    return TL.snap(t, TL.grid_step(float(s.get('bpm', 120)), int(s.get('snapdiv', 1)), float(s.get('fps', 30)), unit))


def _warn_range(show, t, what, warns):
    ln = show['settings'].get('length')
    if ln is not None and (t < 0 or t > float(ln) + 1e-9):
        warns.append('%s t=%s is outside 0..length %s' % (what, _num(t), _num(ln)))


def op_add_key(show, d, ctx, warns):
    lane = _lane(show, d.get('lane'))
    t = _snap(to_seconds(d.get('t'), ctx), d, show)
    v = _finite(d.get('v', d.get('value')), 'v')
    interp = str(d.get('interp', 'linear')).lower()
    if interp not in TL.INTERPS:
        raise OpError('interp must be one of %s' % list(TL.INTERPS))
    if len(lane['keys']) >= MAX_KEYS:
        raise OpError('lane %s is full (%d keys)' % (lane['name'], MAX_KEYS))
    _warn_range(show, t, 'key', warns)
    ks, i = TL.add_key([tuple(k) for k in lane['keys']], t, v, interp)
    lane['keys'] = [list(k) for k in ks]
    return {'lane': lane['name'], 'index': i, 't': t, 'v': v, 'keys': len(ks)}


def op_move_key(show, d, ctx, warns):
    lane = _lane(show, d.get('lane'))
    i = _key_index(lane, d, ctx)
    t0, v0, i0 = lane['keys'][i]
    t = t0
    if d.get('t') is not None:
        t = _snap(to_seconds(d['t'], ctx), d, show)
    elif d.get('by') is not None:
        t = t0 + duration(d['by'], ctx)
    v = _finite(d['v'], 'v') if d.get('v') is not None else v0
    interp = str(d.get('interp', i0)).lower()
    if interp not in TL.INTERPS:
        raise OpError('interp must be one of %s' % list(TL.INTERPS))
    others = [k for j, k in enumerate(lane['keys']) if j != i]
    if any(abs(k[0] - t) <= 1e-4 for k in others):
        raise OpError('lane %s: a key already sits at t=%s (delete it first)' % (lane['name'], _num(t)))
    _warn_range(show, t, 'key', warns)
    ks = sorted(others + [[t, v, interp]], key=lambda k: k[0])
    lane['keys'] = ks
    return {'lane': lane['name'], 'index': ks.index([t, v, interp]), 't': t, 'v': v, 'interp': interp}


def op_delete_key(show, d, ctx, warns):
    lane = _lane(show, d.get('lane'))
    i = _key_index(lane, d, ctx)
    k = lane['keys'].pop(i)
    return {'lane': lane['name'], 'deleted': k, 'keys': len(lane['keys'])}


def op_set_keys(show, d, ctx, warns):
    lane = _lane(show, d.get('lane'))
    lane['keys'] = norm_keys(d.get('keys', []), ctx, 'lane %s keys' % lane['name'])
    return {'lane': lane['name'], 'keys': len(lane['keys'])}


def op_add_lane(show, d, ctx, warns):
    if any(l['name'] == d.get('name') for l in show['lanes']):
        raise OpError('lane %r exists (set_lane changes it)' % d.get('name'))
    ln = norm_lane(d, ctx)
    if not ln['op'] or not ln['par']:
        warns.append('lane %s has no target (op/par): it evaluates but drives nothing' % ln['name'])
    show['lanes'].append(ln)
    return {'lane': ln['name'], 'keys': len(ln['keys']), 'lanes': len(show['lanes'])}


def op_set_lane(show, d, ctx, warns):
    lane = _lane(show, d.get('name', d.get('lane')))
    new = dict(lane)
    for k in ('op', 'par', 'min', 'max', 'enabled'):
        if d.get(k) is not None:
            new[k] = d[k]
    if d.get('target') is not None:
        new['op'], new['par'] = _target(d['target'])
    if d.get('rename') is not None:
        if any(l['name'] == d['rename'] for l in show['lanes'] if l is not lane):
            raise OpError('lane %r exists' % d['rename'])
        new['name'] = d['rename']
    if d.get('keys') is not None:
        new['keys'] = d['keys']
    ln = norm_lane(new, ctx)
    show['lanes'][show['lanes'].index(lane)] = ln
    return {'lane': ln['name'], 'target': '%s.%s' % (ln['op'], ln['par']), 'enabled': ln['enabled']}


def op_delete_lane(show, d, ctx, warns):
    lane = _lane(show, d.get('name', d.get('lane')))
    show['lanes'].remove(lane)
    return {'deleted': lane['name'], 'lanes': len(show['lanes'])}


def op_move_lane(show, d, ctx, warns):
    lane = _lane(show, d.get('name', d.get('lane')))
    to = int(_finite(d.get('to'), 'to'))
    show['lanes'].remove(lane)
    to = min(max(to, 0), len(show['lanes']))
    show['lanes'].insert(to, lane)
    return {'lane': lane['name'], 'index': to}


def op_add_marker(show, d, ctx, warns):
    t = _snap(to_seconds(d.get('t'), ctx), d, show)
    n = _marker_name(d.get('name'))
    if any(m[1] == n for m in show['markers']):
        raise OpError('marker %r exists (names are unique: "@name" times use them)' % n)
    _warn_range(show, t, 'marker', warns)
    show['markers'] = sorted([m for m in show['markers'] if abs(m[0] - t) > 1e-4] + [[t, n]], key=lambda m: m[0])
    ctx.markers = [(m[0], m[1]) for m in show['markers']]
    return {'marker': n, 't': t, 'markers': len(show['markers'])}


def op_move_marker(show, d, ctx, warns):
    i = _marker_index(show, d, ctx)
    t, n = show['markers'][i]
    if d.get('t') is not None:
        t = _snap(to_seconds(d['t'], ctx), d, show)
    elif d.get('by') is not None:
        t = t + duration(d['by'], ctx)
    if d.get('rename') is not None:
        nn = _marker_name(d['rename'])
        if any(m[1] == nn for j, m in enumerate(show['markers']) if j != i):
            raise OpError('marker %r exists' % nn)
        n = nn
    show['markers'][i] = [t, n]
    show['markers'].sort(key=lambda m: m[0])
    ctx.markers = [(m[0], m[1]) for m in show['markers']]
    return {'marker': n, 't': t}


def op_delete_marker(show, d, ctx, warns):
    i = _marker_index(show, d, ctx)
    m = show['markers'].pop(i)
    ctx.markers = [(x[0], x[1]) for x in show['markers']]
    return {'deleted': m[1], 't': m[0]}


def _next_clip_id(show, base='clip'):
    ids = set(c['id'] for c in show['clips'] or [])
    n = len(ids) + 1
    while '%s%d' % (base, n) in ids:
        n += 1
    return '%s%d' % (base, n)


def op_add_clip(show, d, ctx, warns):
    if show.get('clips') is None:
        raise OpError('this timeline has no clips track (phase 2)')
    d = dict(d)
    if not d.get('id'):
        d['id'] = _next_clip_id(show)
    c = norm_clip(d, ctx, set(x['id'] for x in show['clips']))
    _warn_range(show, c['start'] + c['dur'], 'clip end', warns)
    show['clips'].append(c)
    return {'clip': c['id'], 'start': c['start'], 'dur': c['dur'], 'track': c['track']}


def op_set_clip(show, d, ctx, warns):
    c = _clip(show, d.get('id'))
    new = dict(c)
    for k in CLIP_FIELDS:
        if k != 'id' and d.get(k) is not None:
            new[k] = d[k]
    if d.get('end') is not None:
        new['dur'] = to_seconds(d['end'], ctx) - to_seconds(new['start'], ctx)
    if d.get('rename') is not None:
        new['id'] = d['rename']
    nc = norm_clip(new, ctx, set(x['id'] for x in show['clips'] if x is not c))
    show['clips'][show['clips'].index(c)] = nc
    return {'clip': nc['id'], 'start': nc['start'], 'dur': nc['dur'], 'track': nc['track'], 'in': nc['in']}


def op_move_clip(show, d, ctx, warns):
    c = _clip(show, d.get('id'))
    start = c['start']
    if d.get('start') is not None:
        start = _snap(to_seconds(d['start'], ctx), d, show)
    elif d.get('by') is not None:
        start = c['start'] + duration(d['by'], ctx)
    tr = None if d.get('track') is None else int(_finite(d['track'], 'track'))
    nc = CL.move_clip(c, start, tr)
    show['clips'][show['clips'].index(c)] = nc
    _warn_range(show, nc['start'] + nc['dur'], 'clip end', warns)
    return {'clip': nc['id'], 'start': nc['start'], 'track': nc['track']}


def op_trim_clip(show, d, ctx, warns):
    """edge in|out to timeline time t (in slides the source in point, like the strip drag). src_dur limits the out
    edge to the source end when given (the ext fills it from the media json)."""
    c = _clip(show, d.get('id'))
    edge = d.get('edge')
    if edge not in ('in', 'out'):
        raise OpError("edge must be 'in' or 'out'")
    t = _snap(to_seconds(d.get('t'), ctx), d, show)
    nc = CL.trim_clip(c, edge, t, float(d.get('src_dur') or 0.0))
    show['clips'][show['clips'].index(c)] = nc
    return {'clip': nc['id'], 'start': nc['start'], 'dur': nc['dur'], 'in': nc['in']}


def op_delete_clip(show, d, ctx, warns):
    c = _clip(show, d.get('id'))
    show['clips'].remove(c)
    return {'deleted': c['id'], 'clips': len(show['clips'])}


def op_set(show, d, ctx, warns):
    """Settings: {op: 'set', bpm: 128, length: 240, ...} (keys of SETTINGS)."""
    done = {}
    for k, v in d.items():
        if k == 'op':
            continue
        done[k] = coerce_setting(k, v)
    show['settings'].update(done)
    s = show['settings']
    ctx.fps, ctx.bpm, ctx.bpb = float(s.get('fps', ctx.fps)), float(s.get('bpm', ctx.bpm)), int(s.get('beatsperbar', ctx.bpb))
    if 'length' in done:
        ctx.length = done['length']
    return {'set': done}


OPS = {
    'add_key': op_add_key, 'move_key': op_move_key, 'delete_key': op_delete_key, 'set_keys': op_set_keys,
    'add_lane': op_add_lane, 'set_lane': op_set_lane, 'delete_lane': op_delete_lane, 'move_lane': op_move_lane,
    'add_marker': op_add_marker, 'move_marker': op_move_marker, 'delete_marker': op_delete_marker,
    'add_clip': op_add_clip, 'set_clip': op_set_clip, 'move_clip': op_move_clip, 'trim_clip': op_trim_clip,
    'delete_clip': op_delete_clip, 'set': op_set,
}


def apply_ops(show, ops, atomic=True):
    """Apply edit ops to a COPY of show. -> (new show, results, ok). results[i] = {op, ok, ...} or {op, ok: False,
    error}. atomic (default): any error -> the original show comes back unchanged (results still say which op)."""
    if not isinstance(ops, (list, tuple)):
        raise OpError('ops must be a list of {op: ...} objects')
    if len(ops) > MAX_OPS:
        raise OpError('at most %d ops per call' % MAX_OPS)
    new = copy.deepcopy(show)
    ctx = Ctx.of(new)
    results, ok = [], True
    for n, d in enumerate(ops):
        name = d.get('op') if isinstance(d, dict) else None
        fn = OPS.get(name)
        warns = []
        if fn is None:
            results.append({'i': n, 'op': name, 'ok': False,
                            'error': 'unknown op %r (known: %s)' % (name, sorted(OPS))})
            ok = False
            continue
        snap = copy.deepcopy(new) if not atomic else None
        try:
            r = fn(new, d, ctx, warns)
            r = dict(r, i=n, op=name, ok=True)
            if warns:
                r['warnings'] = warns
            results.append(r)
        except OpError as e:
            results.append({'i': n, 'op': name, 'ok': False, 'error': str(e)})
            ok = False
            if snap is not None:
                new = snap   # non-atomic: a failed op leaves no half-change
                ctx = Ctx.of(new)
    if atomic and not ok:
        return copy.deepcopy(show), results, False
    return new, results, ok


# ---------------------------------------------------------------- reading a show (sampling, exports)
def lane_values(show, t):
    """{lane name: value at t} (pure: same maths as lanes_eval)."""
    return dict((ln['name'], TL.lane_value([tuple(k) for k in ln['keys']], t)) for ln in show['lanes'])


def summary(show):
    s = show['settings']
    out = {'lanes': [{'name': l['name'], 'target': '%s.%s' % (l['op'], l['par']), 'keys': len(l['keys']),
                      'enabled': l['enabled']} for l in show['lanes']],
           'markers': len(show['markers']), 'length': s.get('length'), 'bpm': s.get('bpm'), 'fps': s.get('fps')}
    if show.get('clips') is not None:
        out['clips'] = len(show['clips'])
    return out


def frame_times(start, end, fps):
    """Times of every frame in [start, end): ceil((end-start)*fps) frames."""
    n = int(math.ceil((end - start) * fps - 1e-9))
    return [start + i / float(fps) for i in range(max(0, n))]


def lanes_csv(show, start, end, fps, lanes=None):
    """Per-frame lane values: 'frame,time,"<lane>"...' (frame counted from 0 at start)."""
    names = [l['name'] for l in show['lanes'] if lanes is None or l['name'] in lanes]
    keys = dict((l['name'], [tuple(k) for k in l['keys']]) for l in show['lanes'])
    lines = [','.join(['frame', 'time'] + ['"%s"' % n for n in names])]
    for i, t in enumerate(frame_times(start, end, fps)):
        lines.append(','.join([str(i), _num(t)] + [repr(round(TL.lane_value(keys[n], t), 7)) for n in names]))
    return '\n'.join(lines) + '\n', len(lines) - 1, names


def markers_doc(show):
    s = show['settings']
    fps, bpm, bpb = float(s.get('fps', 30)), float(s.get('bpm', 120)), int(s.get('beatsperbar', 4))
    return {'format': 'tl-markers', 'v': 1, 'fps': fps, 'bpm': bpm,
            'markers': [{'t': t, 'name': n, 'frame': TL.frame_of(t, fps), 'smpte': TL.format_tc(t, fps, 'smpte'),
                         'bars': TL.format_tc(t, fps, 'bars', bpm, bpb)} for t, n in show['markers']]}


def markers_csv(show):
    s = show['settings']
    fps = float(s.get('fps', 30))
    lines = ['time,frame,smpte,"name"']
    for t, n in show['markers']:
        lines.append('%s,%d,%s,"%s"' % (_num(t), TL.frame_of(t, fps), TL.format_tc(t, fps, 'smpte'),
                                        n.replace('"', "'")))
    return '\n'.join(lines) + '\n'


def record_plan(start, end, fps, length, cook_rate):
    """Frames + TD cooks for a stepped take of [start, end) at fps (movie) with TD running at cook_rate.
    The timeline advances 1/cook_rate per TD frame during the take (content in real time); the file gets one frame
    per 1/fps of TD timeline time (Movie File Out, T-64), so cooks = frames * cook_rate / fps."""
    if not (1 <= fps <= 240):
        raise OpError('fps must be 1..240')
    if length is not None and end > float(length) + 1e-9:
        raise OpError('end %s is past the timeline length %s' % (_num(end), _num(length)))
    if start < 0 or end <= start:
        raise OpError('need 0 <= start < end, got %s..%s' % (_num(start), _num(end)))
    frames = int(math.ceil((end - start) * fps - 1e-9))
    rate = float(cook_rate) if cook_rate else float(fps)
    return {'start': start, 'end': end, 'fps': float(fps), 'frames': frames,
            'cooks': int(math.ceil(frames * rate / fps)), 'dt': 1.0 / rate, 'cook_rate': rate}


def transport_plan(action, d, cur, ctx, keys_times=()):
    """Transport action -> {par: value} to write (pure). cur = {seek, play, inpoint, outpoint, length, fps}.
    seek: t (any time form) | frame; step: n frames (default 1, negative = back); next/prev marker/key."""
    if action is not None and action not in TRANSPORT_ACTIONS:
        raise OpError('action must be one of %s' % list(TRANSPORT_ACTIONS))
    t = float(cur['seek'])
    a, b = float(cur['inpoint']), float(cur['outpoint'])
    ln = float(cur['length'])
    if b <= a:
        a, b = 0.0, ln
    out = {}
    if action is None:
        pass
    elif action == 'play':
        out['Play'] = True
    elif action == 'pause':
        out['Play'] = False
    elif action == 'toggle':
        out['Play'] = not cur['play']
    elif action == 'stop':
        out['Play'] = False
        out['Seek'] = a
    elif action == 'start':
        out['Seek'] = a
    elif action == 'end':
        out['Seek'] = b
    elif action == 'seek':
        if d.get('frame') is not None:
            nt = _finite(d['frame'], 'frame') / ctx.fps
        else:
            nt = to_seconds(d.get('t'), ctx)
        out['Seek'] = nt
    elif action == 'step':
        out['Seek'] = TL.step_frame(t, ctx.fps, int(_finite(d.get('n', 1), 'n')))
    else:
        times = [m[0] for m in ctx.markers] if action.endswith('marker') else list(keys_times)
        fn = TL.next_time if action.startswith('next') else TL.prev_time
        x = fn(times, t)
        if x is None:
            raise OpError('no %s %s from t=%s' % (action.split('_')[0], action.split('_')[1], _num(t)))
        out['Seek'] = x
    if 'Seek' in out:
        if out['Seek'] < 0 or out['Seek'] > ln + 1e-9:
            raise OpError('seek %s is outside 0..length %s' % (_num(out['Seek']), _num(ln)))
    for k in ('rate', 'loop'):
        if d.get(k) is not None:
            out[k.capitalize()] = coerce_setting(k, d[k])
    for k in ('inpoint', 'outpoint'):
        if d.get(k) is not None:
            out[k.capitalize()] = to_seconds(d[k], ctx)
    return out
