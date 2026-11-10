"""TL_timeline phase 2 pure logic (no td imports): clips track. Copied into the COMP's `tl_clips_logic` Text DAT.

Clips table, active clips + weights (fades, auto crossfades), source frame index, player bank assignment, proxy /
media-info paths and ffmpeg / ffprobe command lines, fit maths and the composite blend (Python mirror of the
compute shader), clip strip geometry + move / trim edits. Tested offline by test/test_timeline_clips.py. Pure ASCII.
"""
import hashlib
import json
import math
import os

CLIP_HEAD = ['id', 'track', 'start', 'dur', 'src', 'in', 'speed', 'fade', 'proxy', 'enabled']
SOURCEMODES = ('full', 'proxy', 'auto')
BLENDMODES = ('over', 'add', 'screen')
FITMODES = ('fit', 'fill', 'stretch')
MAX_PLAYERS = 4          # fixed bank player0..player3
MIN_DUR = 1.0 / 120.0    # shortest clip a trim may leave
EPS = 1e-9


def _f(x, default=0.0):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v or v in (float('inf'), float('-inf')):
        return default
    return v


def _num(x):
    s = '%.6f' % x
    s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


# ---------------------------------------------------------------- clips table
def parse_clips(rows):
    """clips table rows (header required, any column order) -> list of clip dicts in table order.

    Rows without an id / src or with dur <= 0 are skipped. track int >= 0, speed default 1 (0 = freeze frame,
    negative = reverse), fade >= 0, enabled default on. 'row' = table row index (for write-back)."""
    if not rows:
        return []
    head = [str(c).strip().lower() for c in rows[0]]
    if 'id' not in head or 'src' not in head:
        return []
    out = []
    seen = set()
    for ri, r in enumerate(rows[1:], 1):
        d = {h: (str(r[i]).strip() if i < len(r) else '') for i, h in enumerate(head)}
        cid, src = d.get('id', ''), d.get('src', '')
        dur = _f(d.get('dur'), 0.0)
        if not cid or not src or dur <= 0 or cid in seen:
            continue
        seen.add(cid)
        en = d.get('enabled', '1').lower() not in ('0', 'false', 'off', 'no')
        out.append({'id': cid, 'track': max(0, int(_f(d.get('track'), 0.0))), 'start': _f(d.get('start'), 0.0),
                    'dur': dur, 'src': src, 'in': max(0.0, _f(d.get('in'), 0.0)),
                    'speed': _f(d.get('speed'), 1.0) if d.get('speed', '') != '' else 1.0,
                    'fade': max(0.0, _f(d.get('fade'), 0.0)), 'proxy': d.get('proxy', ''), 'enabled': en,
                    'row': ri})
    return out


def clips_to_rows(clips):
    rows = [list(CLIP_HEAD)]
    for c in clips:
        rows.append([c['id'], str(int(c['track'])), _num(c['start']), _num(c['dur']), c['src'], _num(c['in']),
                     _num(c['speed']), _num(c['fade']), c.get('proxy', ''), '1' if c.get('enabled', True) else '0'])
    return rows


def clip_end(c):
    return c['start'] + c['dur']


def layer_order(clips):
    """Bottom first: track ascending, then start ascending, then table order (later clip on top)."""
    return sorted(clips, key=lambda c: (c['track'], c['start'], c.get('row', 0)))


def track_count(clips):
    return max([c['track'] for c in clips] + [-1]) + 1


# ---------------------------------------------------------------- weights (fades + auto crossfades)
def fade_lengths(c, clips):
    """(fade_in, fade_out) of clip c.

    Same track overlap = auto crossfade: the later clip fades in over the whole overlap and the earlier one stays at
    full weight under it (dissolve; midpoint = mean of both with Blendmode over). Without an overlap the clip's own
    `fade` fades from / to transparent at its edges."""
    fi, fo = c['fade'], c['fade']
    s, e = c['start'], clip_end(c)
    for o in clips:
        if o is c or o['id'] == c['id'] or not o.get('enabled', True) or o['track'] != c['track']:
            continue
        os_, oe = o['start'], clip_end(o)
        if os_ < s - EPS and oe > s + EPS:          # an earlier clip still runs when c starts: crossfade in
            fi = min(oe, e) - s
        if os_ > s + EPS and os_ < e - EPS:         # a later clip starts inside c: it covers c, no fade-out
            fo = 0.0
    return max(0.0, fi), max(0.0, fo)


def clip_weight(c, t, clips):
    """0..1 opacity of clip c at timeline time t (0 outside [start, end))."""
    if not c.get('enabled', True):
        return 0.0
    s, e = c['start'], clip_end(c)
    if t < s - EPS or t >= e - EPS:
        return 0.0
    fi, fo = fade_lengths(c, clips)
    w = 1.0
    if fi > EPS:
        w = min(w, (t - s) / fi)
    if fo > EPS:
        w = min(w, (e - t) / fo)
    return min(max(w, 0.0), 1.0)


def active_clips(clips, t):
    """[(clip, weight)] bottom-first for the clips visible at t (weight > 0)."""
    out = []
    for c in layer_order(clips):
        w = clip_weight(c, t, clips)
        if w > 0.0:
            out.append((c, w))
    return out


def upcoming_clips(clips, t, preroll):
    """Enabled clips that start within (t, t + preroll], soonest first (to preload a player)."""
    if preroll <= 0:
        return []
    up = [c for c in clips if c.get('enabled', True) and t + EPS < c['start'] <= t + preroll + EPS]
    return sorted(up, key=lambda c: (c['start'], -c['track']))


# ---------------------------------------------------------------- source time / frame
def source_time(c, t):
    return c['in'] + (t - c['start']) * c['speed']


def source_index(c, t, fps, frames=0):
    """Frame index in the source movie at timeline time t (0-based, clamped to [0, frames-1] when frames known)."""
    if fps <= 0:
        return 0
    i = int(math.floor(source_time(c, t) * fps + 1e-4))
    if frames and frames > 0:
        i = min(i, int(frames) - 1)
    return max(i, 0)


def source_span_ok(c, media):
    """False when the clip asks for source time past the end of the movie (it then holds the last frame)."""
    dur = _f((media or {}).get('dur'), 0.0)
    if dur <= 0:
        return True
    a, b = source_time(c, c['start']), source_time(c, clip_end(c))
    return min(a, b) >= -EPS and max(a, b) <= dur + 1e-3


# ---------------------------------------------------------------- player bank
def assign_players(want, prev, nslots):
    """Stable assignment of clip ids to player slots.

    want = ids in priority order (most important first); prev = {id: slot} from the last frame. Ids that keep their
    slot do not reload their file. Returns {id: slot} for at most nslots ids (lowest priority ids dropped)."""
    nslots = max(0, min(int(nslots), MAX_PLAYERS))
    keep_ids = []
    for i in want:
        if i not in keep_ids:
            keep_ids.append(i)
    keep_ids = keep_ids[:nslots]
    out = {}
    used = set()
    for i in keep_ids:
        s = prev.get(i)
        if s is not None and 0 <= s < nslots and s not in used:
            out[i] = s
            used.add(s)
    free = [s for s in range(nslots) if s not in used]
    for i in keep_ids:
        if i not in out and free:
            out[i] = free.pop(0)
    return out


def use_proxy(mode, has_proxy, scrubbing):
    if not has_proxy:
        return False
    if mode == 'proxy':
        return True
    if mode == 'auto':
        return bool(scrubbing)
    return False


def plan(clips, t, nslots, prev, media=None, preroll=0.5, sourcemode='full', scrubbing=False, fps_default=30.0,
         root=''):
    """Everything the TD side writes for one frame.

    Returns {'slots': [None | {'id','file','index','weight','rank','proxy'}] * nslots, 'assign': {id: slot},
             'active': [ids bottom-first], 'dropped': [ids visible but without a player]}.
    Visible clips get players topmost first; free players preload upcoming clips (weight 0, index at their in point).
    rank = compositing order (0 = bottom) among the visible clips that got a player."""
    media = media or {}
    nslots = max(0, min(int(nslots), MAX_PLAYERS))
    act = active_clips(clips, t)
    top_first = [c['id'] for c, _ in reversed(act)]
    up = [c['id'] for c in upcoming_clips(clips, t, preroll)]
    assign = assign_players(top_first + up, prev or {}, nslots)
    by_id = dict((c['id'], c) for c in clips)
    slots = [None] * nslots
    rank = 0
    weights = dict((c['id'], w) for c, w in act)
    for c, w in act:                                 # bottom first -> ranks
        if c['id'] in assign:
            slots[assign[c['id']]] = {'id': c['id'], 'weight': w, 'rank': rank}
            rank += 1
    for cid, s in assign.items():
        if slots[s] is None:
            slots[s] = {'id': cid, 'weight': 0.0, 'rank': -1}
    for s, d in enumerate(slots):
        if d is None:
            continue
        c = by_id[d['id']]
        src = resolve_path(c['src'], root)
        m = media.get(src, {})
        fps = _f(m.get('fps'), 0.0) or fps_default
        tt = t if weights.get(c['id'], 0.0) > 0 else c['start']
        px = proxy_for(c, root, media)
        prox = use_proxy(sourcemode, bool(px), scrubbing)
        d['file'] = px if prox else src
        d['proxy'] = prox
        d['index'] = source_index(c, tt, fps, int(_f(m.get('frames'), 0)))
    dropped = [c['id'] for c, _ in act if c['id'] not in assign]
    return {'slots': slots, 'assign': assign, 'active': [c['id'] for c, _ in act], 'dropped': dropped}


# ---------------------------------------------------------------- paths, media info, proxies (ffmpeg off TD's cook)
def resolve_path(p, root):
    p = str(p).strip()
    if not p or os.path.isabs(p) or not root:
        return p
    return os.path.normpath(os.path.join(root, p))


def media_key(abspath):
    return hashlib.sha1(abspath.encode('utf-8')).hexdigest()[:16]


def media_info_path(abspath, cache_dir):
    """JSON written by tools/timeline_media.py for one source: {src, fps, frames, w, h, dur, proxy}."""
    return os.path.join(cache_dir, media_key(abspath) + '.json')


def proxy_path(abspath, proxy_dir):
    """Default proxy file: <proxy_dir>/<key>/<name>_proxy.mp4 (key keeps two sources with one name apart)."""
    stem = os.path.splitext(os.path.basename(abspath))[0]
    return os.path.join(proxy_dir, media_key(abspath), stem + '_proxy.mp4')


def proxy_for(c, root, media):
    """Proxy file for clip c: the `proxy` column (path) when set, else the one the media info names ('' = none)."""
    p = str(c.get('proxy', '')).strip()
    if p and p.lower() not in ('auto', 'none', '0'):
        return resolve_path(p, root)
    if p.lower() == 'none':
        return ''
    m = (media or {}).get(resolve_path(c['src'], root), {})
    return str(m.get('proxy', '') or '')


def proxy_cmd(src, dst, ffmpeg='ffmpeg', scale=0.5, crf=20):
    """All-Intra H.264 proxy (every frame a keyframe: exact, cheap seeks), same fps and frame count, no audio."""
    sc = max(0.05, min(1.0, float(scale)))
    vf = 'scale=trunc(iw*%s/2)*2:trunc(ih*%s/2)*2' % (_num(sc), _num(sc))
    return [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-map', '0:v:0', '-vf', vf,
            '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'fastdecode', '-crf', str(int(crf)),
            '-g', '1', '-bf', '0', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', dst]


def probe_cmd(src, ffprobe='ffprobe'):
    return [ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_packets',
            '-show_entries', 'stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_packets,duration'
            ':format=duration', '-of', 'json', src]


def _rate(s):
    s = str(s or '')
    if '/' in s:
        a, b = s.split('/', 1)
        return _f(a) / _f(b) if _f(b) else 0.0
    return _f(s)


def parse_probe(text):
    """ffprobe json -> {fps, frames, w, h, dur} (frames from nb_frames, else counted packets, else dur * fps)."""
    try:
        d = json.loads(text)
    except ValueError:
        return {}
    st = (d.get('streams') or [{}])[0]
    fps = _rate(st.get('avg_frame_rate')) or _rate(st.get('r_frame_rate'))
    dur = _f(st.get('duration'), 0.0) or _f((d.get('format') or {}).get('duration'), 0.0)
    frames = int(_f(st.get('nb_frames'), 0.0)) or int(_f(st.get('nb_read_packets'), 0.0))
    if not frames and fps > 0 and dur > 0:
        frames = int(round(dur * fps))
    if fps > 0 and frames and not dur:
        dur = frames / fps
    return {'fps': fps, 'frames': frames, 'w': int(_f(st.get('width'), 0)), 'h': int(_f(st.get('height'), 0)),
            'dur': dur}


# ---------------------------------------------------------------- fit + blend (mirror of the compute shader)
def fit_scale(sw, sh, dw, dh, mode='fit'):
    """(sx, sy): source uv = 0.5 + (out uv - 0.5) * (sx, sy). fit = whole source visible (bars), fill = cover
    (crop), stretch = (1, 1)."""
    if mode == 'stretch' or min(sw, sh, dw, dh) <= 0:
        return 1.0, 1.0
    s = min(dw / float(sw), dh / float(sh)) if mode == 'fit' else max(dw / float(sw), dh / float(sh))
    return dw / (sw * s), dh / (sh * s)


def straight_to_premult(px):
    r, g, b, a = px
    return (r * a, g * a, b * a, a)


def composite_pixel(layers, mode='over', premult_inputs=True):
    """layers = [(rgba, weight)] bottom-first -> premultiplied rgba. Starts transparent black.

    over: s = src*w, acc = s + acc*(1 - s.a); add: acc += src*w (alpha clamped); screen: rgb 1-(1-acc)(1-s),
    alpha like over. premult_inputs: the sources are straight alpha and get premultiplied first."""
    acc = [0.0, 0.0, 0.0, 0.0]
    for px, w in layers:
        if w <= 0:
            continue
        p = straight_to_premult(px) if premult_inputs else tuple(px)
        s = [x * w for x in p]
        if mode == 'add':
            acc = [acc[0] + s[0], acc[1] + s[1], acc[2] + s[2], min(1.0, acc[3] + s[3])]
        elif mode == 'screen':
            acc = [1 - (1 - acc[i]) * (1 - s[i]) for i in range(3)] + [s[3] + acc[3] * (1 - s[3])]
        else:
            acc = [s[i] + acc[i] * (1 - s[3]) for i in range(4)]
    return tuple(acc)


def menu_index(items, value):
    try:
        return list(items).index(value)
    except ValueError:
        return 0


# ---------------------------------------------------------------- clip strip (u right, v up, 0..1)
STRIP_PAD = 0.12          # fraction of a track band left empty top and bottom


def track_band(track, ntracks):
    """(v_bottom, v_top) of a track row; track 0 is the bottom row (higher tracks draw on top, like layers)."""
    n = max(1, int(ntracks))
    h = 1.0 / n
    return track * h, (track + 1) * h


def clip_rect(c, length, ntracks):
    """(u0, u1, v0, v1) of the clip bar in the strip."""
    ln = max(length, EPS)
    b, t = track_band(c['track'], ntracks)
    pad = (t - b) * STRIP_PAD
    return c['start'] / ln, clip_end(c) / ln, b + pad, t - pad


def clip_at(clips, u, v, length, ntracks, w_px=1024.0, edge_px=6.0):
    """(clip index, part) under (u, v): part 'in' / 'out' within edge_px of an edge, else 'body'. (-1, '') if none.
    The topmost bar wins (layer order reversed)."""
    order = list(range(len(clips)))
    order.sort(key=lambda i: (clips[i]['track'], clips[i]['start'], clips[i].get('row', 0)), reverse=True)
    eu = edge_px / max(w_px, 1.0)
    for i in order:
        u0, u1, v0, v1 = clip_rect(clips[i], length, ntracks)
        if v0 <= v <= v1 and u0 - eu <= u <= u1 + eu:
            if abs(u - u0) <= eu and (u1 - u0) > 2 * eu:
                return i, 'in'
            if abs(u - u1) <= eu:
                return i, 'out'
            if u0 <= u <= u1:
                return i, 'body'
    return -1, ''


def track_at(v, ntracks):
    n = max(1, int(ntracks))
    return min(max(int(v * n), 0), n - 1)


def move_clip(c, start, track=None):
    """Copy of c moved to start (>= 0) and optionally to another track."""
    d = dict(c)
    d['start'] = max(0.0, start)
    if track is not None:
        d['track'] = max(0, int(track))
    return d


def trim_clip(c, edge, t, src_dur=0.0, min_dur=MIN_DUR):
    """Copy of c with its in edge or out edge moved to timeline time t. The in edge keeps the out edge where it is
    and slides the source in point with it (never before source 0); src_dur > 0 limits the out edge to the end of
    the source. speed 0 (freeze) only limits by min_dur."""
    d = dict(c)
    sp = c['speed']
    end = clip_end(c)
    if edge == 'in':
        lo = -1e18
        if sp > 0:
            lo = c['start'] - c['in'] / sp            # source time 0
        elif sp < 0 and src_dur > 0:
            lo = c['start'] - (src_dur - c['in']) / -sp
        ns = min(max(t, lo, 0.0), end - min_dur)
        d['in'] = max(0.0, c['in'] + (ns - c['start']) * sp)
        d['start'] = ns
        d['dur'] = end - ns
    else:
        hi = 1e18
        if src_dur > 0 and sp > 0:
            hi = c['start'] + (src_dur - c['in']) / sp
        elif sp < 0:
            hi = c['start'] + c['in'] / -sp
        ne = max(min(t, hi), c['start'] + min_dur)
        d['dur'] = ne - c['start']
    return d


def strip_tracks(clips):
    """Rows in the clip strip: used tracks + one empty row on top to drag clips onto."""
    return track_count(clips) + 1


def strip_rows(clips, length, selected=''):
    """Strip shader data, one sample per clip, bottom-first draw order: u0, u1, track (+0.5 = disabled), flag
    (1 = selected). No time in here (the shader gets the playhead as a uniform), so it recooks only on edits."""
    u0s, u1s, trs, flags = [], [], [], []
    for c in layer_order(clips):
        u0, u1, _, _ = clip_rect(c, length, 1)
        u0s.append(u0)
        u1s.append(u1)
        trs.append(float(c['track']) + (0.0 if c.get('enabled', True) else 0.5))
        flags.append(1.0 if c['id'] == selected else 0.0)
    return {'u0': u0s, 'u1': u1s, 'tr': trs, 'flag': flags}


def strip_labels(clips, length, ntracks, w_px, h_px):
    """Text TOP spec rows (text, x, y from bottom) naming each clip bar at its left edge."""
    rows = [['text', 'x', 'y']]
    for c in layer_order(clips):
        u0, u1, v0, v1 = clip_rect(c, length, ntracks)
        if (u1 - u0) * w_px < 18:
            continue
        rows.append([c['id'], str(int(u0 * w_px) + 6), str(int((v0 + v1) * 0.5 * h_px) - 6)])
    return rows
