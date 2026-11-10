# lyrics_feed_logic - pure logic for LY_lyrics_feed (no td import; tested offline in test/test_lyrics_feed.py).
# Spec: docs/research/AS_spotifybridge_lyrics.md section 7 (local-only: Spotify desktop via osascript + local .lrc).
# Copied into the COMP's `ly_logic` Text DAT by builders/lyrics_feed.py. ASCII source; handles UTF-8 text (Urdu).
import bisect
import os
import re
import unicodedata

# ---------------------------------------------------------------- LRC parsing
_TS = re.compile(r'\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]')
_TAG = re.compile(r'^\[([A-Za-z#]+)\s*:(.*)\]\s*$')
_WORD = re.compile(r'<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>')     # enhanced LRC word stamps: dropped


def _secs(m, s, frac):
    t = int(m) * 60 + int(s)
    if frac:
        t += int(frac) / (10.0 ** len(frac))
    return float(t)


def parse_lrc(text):
    """LRC text -> {'lines': [(t, text), ...] sorted by t (stable), 'tags': {ti, ar, al, length, offset, ...}}.
    Handles a UTF-8 BOM, CRLF, several stamps per line, [mm:ss], [mm:ss.x..xxx], [mm:ss:xx], enhanced <..> word
    stamps, and the [offset:+/-ms] tag (positive = lines earlier, LRC convention). Blank-text stamps are kept (an
    empty line clears the display at that time)."""
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'replace')
    text = text.lstrip(u'\ufeff')
    tags, rows = {}, []
    for raw in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = raw.strip()
        if not line:
            continue
        stamps = []
        pos = 0
        while True:
            m = _TS.match(line, pos)
            if not m:
                break
            stamps.append(_secs(m.group(1), m.group(2), m.group(3)))
            pos = m.end()
            while pos < len(line) and line[pos] == ' ' and _TS.match(line, pos + 1):
                pos += 1
        if stamps:
            body = _WORD.sub('', line[pos:]).strip()
            body = re.sub(r'\s{2,}', ' ', body)
            for t in stamps:
                rows.append((t, body))
            continue
        m = _TAG.match(line)
        if m:
            tags[m.group(1).lower()] = m.group(2).strip()
    off = 0.0
    try:
        off = float(tags.get('offset', '0') or 0) / 1000.0
    except ValueError:
        off = 0.0
    rows = [(max(0.0, t - off), s) for t, s in rows]
    order = sorted(range(len(rows)), key=lambda k: (rows[k][0], k))
    return {'lines': [rows[k] for k in order], 'tags': tags}


def parse_length(tags):
    """[length: mm:ss] or [length: ss] -> seconds, else None."""
    v = (tags or {}).get('length', '').strip()
    if not v:
        return None
    m = re.match(r'^(\d+):(\d{1,2}(?:\.\d+)?)$', v)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    try:
        return float(v)
    except ValueError:
        return None


def song_length(doc):
    """Song length for the manual clock: [length:] tag, else last line + 5 s (0 when no lines)."""
    n = parse_length(doc.get('tags'))
    if n:
        return float(n)
    lines = doc.get('lines') or []
    return (lines[-1][0] + 5.0) if lines else 0.0


# ---------------------------------------------------------------- line lookup
def line_index(times, pos):
    """Index of the line showing at pos (last start <= pos), -1 before the first line."""
    return bisect.bisect_right(times, pos) - 1


def line_state(lines, pos, length=0.0):
    """Everything the outputs need at song position pos (seconds)."""
    times = [t for t, _ in lines]
    i = line_index(times, pos) if lines else -1
    n = len(lines)
    cur = lines[i][1] if i >= 0 else ''
    prev = lines[i - 1][1] if i >= 1 else ''
    nxt = lines[i + 1][1] if 0 <= i + 1 < n else ''
    start = lines[i][0] if i >= 0 else 0.0
    if i + 1 < n:
        end = lines[i + 1][0]
    else:
        end = max(length, start) if length and length > start else start + 5.0
    span = end - start
    prog = 0.0 if i < 0 else (min(1.0, max(0.0, (pos - start) / span)) if span > 1e-6 else 1.0)
    next_in = (lines[i + 1][0] - pos) if i + 1 < n else -1.0
    sp = min(1.0, max(0.0, pos / length)) if length and length > 0 else 0.0
    return {'idx': i, 'count': n, 'cur': cur, 'next': nxt, 'prev': prev, 'line_start': start, 'line_end': end,
            'line_progress': prog, 'next_in': next_in, 'song_progress': sp}


# ---------------------------------------------------------------- script detection (Urdu / Arabic script -> RTL)
def is_rtl(s):
    """True when the text's first strong-direction letter is right-to-left (Arabic script incl. Urdu, Hebrew)."""
    for ch in s or '':
        b = unicodedata.bidirectional(ch)
        if b in ('R', 'AL'):
            return True
        if b == 'L':
            return False
    return False


# ---------------------------------------------------------------- Spotify (osascript) now-playing
SEP = '\x1f'   # ASCII unit separator: never inside a title

APPLESCRIPT = (
    'if application "Spotify" is running then\n'
    ' tell application "Spotify"\n'
    '  set s to (player state as string)\n'
    '  if s is "stopped" then return "stopped"\n'
    '  set t to current track\n'
    '  set sep to (ASCII character 31)\n'
    '  return s & sep & (name of t) & sep & (artist of t) & sep & ((player position) as string) & sep & '
    '((duration of t) as string) & sep & (id of t)\n'
    ' end tell\n'
    'else\n'
    ' return "notrunning"\n'
    'end if\n')


def _num(s):
    s = (s or '').strip().replace(',', '.')          # locale decimal comma
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_now_playing(rc, out, err):
    """osascript result -> {'ok', 'state', 'title', 'artist', 'pos', 'dur', 'id', 'error'} (pos, dur in seconds)."""
    out = (out or '').strip('\r\n')
    d = {'ok': False, 'state': 'unknown', 'title': '', 'artist': '', 'pos': 0.0, 'dur': 0.0, 'id': '', 'error': ''}
    if rc != 0:
        e = (err or '').strip()
        d['state'] = 'noperm' if ('-1743' in e or 'Not authori' in e) else 'error'
        d['error'] = e[-200:]
        return d
    if out in ('notrunning', 'stopped'):
        d['ok'] = True
        d['state'] = out
        return d
    f = out.split(SEP)
    if len(f) < 6:
        d['state'] = 'error'
        d['error'] = 'unexpected reply: ' + out[:120]
        return d
    d.update(ok=True, state=f[0].strip(), title=f[1], artist=f[2], pos=_num(f[3]), id=f[5].strip())
    dur = _num(f[4])
    d['dur'] = dur / 1000.0 if dur > 10000 else dur      # Spotify reports ms
    return d


# ---------------------------------------------------------------- clock
def clock_spotify(st, now, poll, drift=0.3):
    """Interpolated Spotify position. st = previous {'pos','t','playing','id'} or None; poll = parsed reply plus
    'stamp' (same clock as now, mid-point of the osascript call) or None (no new poll). Resyncs when the predicted
    position is off by more than drift s, on play/pause and on a track change; otherwise runs free (smooth).
    Returns (st, pos, resynced)."""
    if st is None:
        st = {'pos': 0.0, 't': now, 'playing': False, 'id': ''}
    pred = st['pos'] + ((now - st['t']) if st['playing'] else 0.0)
    resync = False
    if poll is not None and poll.get('ok') and poll.get('state') in ('playing', 'paused'):
        playing = poll['state'] == 'playing'
        meas = poll['pos'] + ((now - poll.get('stamp', now)) if playing else 0.0)
        if poll.get('id') != st['id'] or playing != st['playing'] or abs(meas - pred) > drift:
            st = {'pos': meas, 't': now, 'playing': playing, 'id': poll.get('id', '')}
            return st, meas, True
    elif poll is not None and poll.get('ok') and poll.get('state') in ('stopped', 'notrunning'):
        st = {'pos': 0.0, 't': now, 'playing': False, 'id': ''}
        return st, 0.0, True
    st = {'pos': pred, 't': now, 'playing': st['playing'], 'id': st['id']}
    return st, pred, resync


def clock_manual(st, now, play, rate, length, loop, events=()):
    """Manual clock: runs while play, at rate (any value, negative runs back). events: ('seek', s) / ('restart',).
    Loops to 0 at length when loop (length > 0), else holds at length. Returns (st, pos)."""
    if st is None:
        st = {'pos': 0.0, 't': now}
    pos = st['pos'] + ((now - st['t']) * rate if play else 0.0)
    for e in events:
        if e[0] == 'seek':
            pos = float(e[1])
        elif e[0] == 'restart':
            pos = 0.0
    if length and length > 0:
        if loop:
            pos = pos % length
        else:
            pos = min(max(pos, 0.0), length)
    else:
        pos = max(pos, 0.0)
    return {'pos': pos, 't': now}, pos


# ---------------------------------------------------------------- finding the .lrc for a track
_JUNK = re.compile(r'\s*[\(\[][^\)\]]*(feat\.?|ft\.?|remaster|live|version|edit|mix|from)[^\)\]]*[\)\]]', re.I)
_DASHJUNK = re.compile(r'\s+-\s+.*(remaster|version|edit|live|mono|stereo|mix).*$', re.I)


def norm(s):
    """Loose key: NFKC, casefold, drop (feat..)/(remastered..)/' - 2011 Remaster', punctuation -> single spaces.
    Letters of every script (Urdu too) are kept."""
    s = unicodedata.normalize('NFKC', s or '')
    s = _JUNK.sub('', s)
    s = _DASHJUNK.sub('', s)
    s = s.casefold()
    s = ''.join(ch if (ch.isalnum() or ch.isspace()) else ' ' for ch in s)
    return ' '.join(s.split())


def track_keys(track_id, artist, title):
    """Candidate keys for a track, best first."""
    keys = []
    tid = (track_id or '').strip()
    if tid:
        keys.append(('id', tid.split(':')[-1]))
        keys.append(('id', tid.replace(':', '_')))
    first_artist = (artist or '').split(',')[0].split('&')[0]
    for a in (artist, first_artist):
        if a and title:
            keys.append(('at', norm(a) + ' - ' + norm(title)))
    if title:
        keys.append(('t', norm(title)))
    return keys


def index_entry(filename, tags=None):
    """Keys one .lrc file answers to: its stem (as id), 'artist - title' from the name, and from [ar:]/[ti:] tags."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    out = [('id', stem)]
    if ' - ' in stem:
        a, t = stem.split(' - ', 1)
        out.append(('at', norm(a) + ' - ' + norm(t)))
        out.append(('t', norm(t)))
    else:
        out.append(('t', norm(stem)))
    tags = tags or {}
    if tags.get('ti'):
        out.append(('t', norm(tags['ti'])))
        if tags.get('ar'):
            out.append(('at', norm(tags['ar']) + ' - ' + norm(tags['ti'])))
    return out


def build_index(entries):
    """entries = [(path, tags)] -> {key: path}; the first file claiming a key wins (sorted by path)."""
    idx = {}
    for path, tags in sorted(entries, key=lambda e: e[0]):
        for k in index_entry(path, tags):
            idx.setdefault(k, path)
    return idx


def find_lrc(index, track_id, artist, title):
    for k in track_keys(track_id, artist, title):
        if k in index:
            return index[k]
    return None


# ---------------------------------------------------------------- source choice
def pick_source(mode, poll, chop_ok):
    """mode auto/spotify/manual/chop -> the clock in use. auto = Spotify when it reports a track
    (playing or paused), else the CHOP clock when wired, else manual."""
    if mode in ('spotify', 'manual', 'chop'):
        return mode
    if poll is not None and poll.get('ok') and poll.get('state') in ('playing', 'paused'):
        return 'spotify'
    return 'chop' if chop_ok else 'manual'
