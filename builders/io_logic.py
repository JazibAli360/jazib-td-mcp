# io_logic - pure logic for BP_io_router (spec: docs/research/BP_ndi_syphon_spout_video_io.md section 3).
# No `td` import; numpy only inside convert_alpha. ASCII only. Tests: test/test_io_logic.py.
# v1 subset: alpha table + numpy reference, NDI name match, route planning (reports only), bandwidth / Hap sizing,
# record presets + pump_cooks, bus fade state machine + beat quantisation, status rows.
import math
import re

SOURCE_KINDS = ['off', 'local', 'ndi', 'syphon', 'movie', 'test']
SINK_KINDS = ['off', 'syphon', 'ndi']
ALPHAS = ['premult', 'straight', 'none']
SINK_SRCS = ['s1', 's2', 's3', 's4', 'bus']
RES_NAMES = ['input', '1080x1920', '1920x1080', '3840x2160', 'custom']
FITS = ['fitbest', 'fill', 'native']
XFADE_MODES = ['manual', 'bpm']
CUT_DIVS = ['0.25', '0.5', '1', '2', '4']
CURVES = ['linear', 'smooth']

# GLSL alpha pass modes (shader in builders/io_router.py, same as spec 3.5)
M_UNPREMULT, M_PREMULT, M_DROP_PREMULT, M_DROP_STRAIGHT, M_PASS = 0, 1, 2, 3, 4


def alpha_mode(src, dst):
    """Shader mode turning a `src` alpha picture into `dst`. Same outcomes as handlers.alpha_step:
    equal -> pass; ->premult = premultiply; ->straight = un-premultiply; ->none = drop alpha over black."""
    if src not in ALPHAS or dst not in ALPHAS:
        raise ValueError('alpha must be one of %s' % ALPHAS)
    if src == dst or src == 'none':
        return M_PASS                     # an opaque picture is both premult and straight
    if dst == 'premult':
        return M_PREMULT
    if dst == 'straight':
        return M_UNPREMULT
    return M_DROP_PREMULT if src == 'premult' else M_DROP_STRAIGHT


def convert_alpha(rgba8, src, dst):
    """numpy reference of the shader on uint8 RGBA (round half up, a=0 safe)."""
    import numpy as np
    m = alpha_mode(src, dst)
    x = np.asarray(rgba8, dtype=np.float64) / 255.0
    rgb, a = x[..., :3], x[..., 3:4]
    if m == M_UNPREMULT:
        rgb = np.where(a > 1e-4, rgb / np.maximum(a, 1e-4), 0.0)
    elif m == M_PREMULT:
        rgb = rgb * a
    elif m == M_DROP_PREMULT:
        a = np.ones_like(a)
    elif m == M_DROP_STRAIGHT:
        rgb, a = rgb * a, np.ones_like(a)
    out = np.concatenate([np.clip(rgb, 0, 1), a], axis=-1)
    return np.floor(out * 255.0 + 0.5).astype(np.uint8)


def composite(rgba8, bg8, model):
    """Receiver composite of rgba8 over bg8 (uint8 rgb) under model premult | straight."""
    import numpy as np
    x = np.asarray(rgba8, dtype=np.float64) / 255.0
    bg = np.asarray(bg8, dtype=np.float64) / 255.0
    rgb, a = x[..., :3], x[..., 3:4]
    o = rgb + bg * (1 - a) if model == 'premult' else rgb * a + bg * (1 - a)
    return np.floor(np.clip(o, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def parse_res(name, w=0, h=0):
    """(w, h) or None for 'input'."""
    if name == 'input':
        return None
    if name == 'custom':
        return (max(1, int(w)), max(1, int(h)))
    a, b = name.split('x')
    return (int(a), int(b))


def ndi_source_name(host, sender):
    return '%s (%s)' % (host, sender) if host else sender


def match_source(names, pattern, prefer_host=''):
    """First NDI source matching pattern (exact > regex > substring); prefer_host breaks ties. None if none."""
    names = [n for n in names if n]
    if not pattern:
        return None
    if pattern in names:
        return pattern
    try:
        rx = re.compile(pattern)
        hits = [n for n in names if rx.search(n)]
    except re.error:
        hits = []
    if not hits:
        hits = [n for n in names if pattern.lower() in n.lower()]
    if not hits:
        return None
    if prefer_host:
        pref = [n for n in hits if n.upper().startswith(prefer_host.upper() + ' (')]
        if pref:
            return pref[0]
    return hits[0]


def plan_routes(sources, sinks):
    """sources: [{kind, name}] x4; sinks: [{kind, src, name, active}] x4. Returns {routes, issues}; never raises on
    content (issues are reported, nothing is blocked)."""
    issues = []
    routes = []
    seen = {}
    for i, o in enumerate(sinks):
        n = i + 1
        kind = o.get('kind', 'off')
        src = o.get('src', 's1')
        name = o.get('name', '')
        routes.append({'sink': 'o%d' % n, 'kind': kind, 'src': src, 'name': name, 'active': bool(o.get('active'))})
        if kind == 'off':
            continue
        if kind in ('syphon', 'ndi'):
            key = (kind, name)
            if key in seen:
                issues.append('o%d: same %s sender name as o%d (%s)' % (n, kind, seen[key], name))
            else:
                seen[key] = n
        # loopback: a sink feeding a source of the same kind with the same name
        used = [int(src[1]) - 1] if src.startswith('s') else [0, 1, 2, 3]
        for k in used:
            s = sources[k] if k < len(sources) else {}
            if s.get('kind') == kind and s.get('name') and (s.get('name') == name or s.get('name').endswith('(%s)' % name)):
                issues.append('o%d: loopback, its source s%d receives this sender (%s)' % (n, k + 1, name))
    for i, s in enumerate(sources):
        if s.get('kind') == 'movie' and not s.get('file'):
            issues.append('s%d: movie kind without a file' % (i + 1))
    return {'routes': routes, 'issues': issues}


HAP_BPP = {'hap': 0.5, 'hapa': 1.0, 'hapq': 1.0, 'hapqa': 1.5}


def estimate_bandwidth(w, h, fps, fmt='rgba8'):
    """Bytes/s (raw formats, Hap family) or bits/s guide for NDI; ProRes -> None (unknown)."""
    px = w * h
    if fmt == 'rgba8':
        return px * 4 * fps
    if fmt == 'rgba16f':
        return px * 8 * fps
    if fmt in HAP_BPP:
        return int(px * HAP_BPP[fmt]) * fps
    if fmt == 'ndi':                       # rough: 150 Mbit/s per 1080p60, scaled by pixels and fps
        return 150e6 * (px / (1920.0 * 1080)) * (fps / 60.0)
    return None


def hap_frame_bytes(w, h, fmt):
    return int(w * h * HAP_BPP[fmt])


# Movie File Out presets (31550 menu tokens; feed rgba8fixed except where stated). Used by the record sink (v2).
CODECS_31550 = ['rle', 'mjpa', 'mpeg4', 'h264', 'cineform', 'hap', 'h265', 'gif', 'notchlc', 'vp8', 'vp9', 'prores',
                'vvc', 'av1']
RECORD_PRESETS = {
    'prores4444': {'videocodec': 'prores', 'type': '4444', 'container': 'mov', 'alpha': True},
    'prores422hq': {'videocodec': 'prores', 'type': '422hq', 'container': 'mov', 'alpha': False},
    'hapq': {'videocodec': 'hap', 'type': 'hapq', 'container': 'mov', 'alpha': False},
    'hapqa': {'videocodec': 'hap', 'type': 'hapqalpha', 'container': 'mov', 'alpha': True},
    'hap': {'videocodec': 'hap', 'type': 'hap', 'container': 'mov', 'alpha': False},
    'hapa': {'videocodec': 'hap', 'type': 'hapalpha', 'container': 'mov', 'alpha': True},
    'h264hw': {'videocodec': 'h264', 'type': '', 'container': 'mp4', 'alpha': False},
}


def pump_cooks(frames, cook_rate, fps):
    """T-64: Movie File Out writes by timeline time -> frames * cook_rate / fps cooks (ceil)."""
    return int(math.ceil(frames * float(cook_rate) / float(fps)))


# ---- bus ---------------------------------------------------------------------------------------------------------

def fade_curve(x, curve='linear'):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x) if curve == 'smooth' else x


def next_boundary(t, bpm, div):
    """Next beat-division boundary strictly after t (seconds; beat 0 at t=0)."""
    period = 60.0 / max(1e-6, float(bpm)) * float(div)
    k = math.floor(t / period + 1e-9) + 1
    return k * period


def bus_step(st, t, p, events=()):
    """Bus fade state machine. st = None or dict; p = {mode, mix, bpm, div, xfadetime, curve}.
    manual: out = mix. bpm: 'cut' event (Cutnow) arms a fade to the other side, starting at the next division
    boundary and lasting xfadetime (0 = hard cut). Returns (st, {'mix', 'target', 'armed', 'fading'})."""
    if st is None:
        st = {'pos': 0.0, 'target': 0.0, 'start': None, 'from': 0.0}
    mode = p.get('mode', 'manual')
    if mode == 'manual':
        st = {'pos': float(p.get('mix', 0.0)), 'target': float(p.get('mix', 0.0)), 'start': None, 'from': 0.0}
        return st, {'mix': st['pos'], 'target': st['target'], 'armed': 0, 'fading': 0}
    if 'cut' in events and st['start'] is None:
        st['from'] = st['pos']
        st['target'] = 0.0 if st['pos'] >= 0.5 else 1.0
        st['start'] = next_boundary(t, p.get('bpm', 120.0), p.get('div', 1.0))
    armed = fading = 0
    if st['start'] is not None:
        if t < st['start']:
            armed = 1
        else:
            ft = float(p.get('xfadetime', 0.0))
            x = 1.0 if ft <= 0 else (t - st['start']) / ft
            if x >= 1.0:
                st['pos'] = st['target']
                st['start'] = None
            else:
                fading = 1
                st['pos'] = st['from'] + (st['target'] - st['from']) * fade_curve(x, p.get('curve', 'linear'))
    return st, {'mix': st['pos'], 'target': st['target'], 'armed': armed, 'fading': fading}


# ---- status ------------------------------------------------------------------------------------------------------

STATUS_COLS = ['id', 'kind', 'name', 'active', 'w', 'h', 'fps', 'queue', 'missed', 'skipped', 'cookms', 'stale',
               'alpha', 'note']


def status_row(**kw):
    return [str(kw.get(c, '')) for c in STATUS_COLS]


def frame_hash_stale(prev_hash, cur_hash, stale_s, dt):
    """Seconds the picture has not changed (identical hash adds dt, a change resets)."""
    return stale_s + dt if prev_hash is not None and prev_hash == cur_hash else 0.0
