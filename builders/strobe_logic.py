"""strobe_logic: pure trigger + envelope logic for FX_strobe (no td import; tested by test/test_strobe.py).

Clean-room design, spec docs/research/AX_strobber.md (idea borrowed from Strobber by Skywalker.Visuals: LFO or audio
trigger -> eased flash alpha -> blend modes; every-Nth-trigger division). No limits: every range is open, no flash
cap, no refractory period unless the operator sets Hold. ASCII only. Copied into the COMP's `strobe_logic` Text DAT.

step(st, t, inp, p, events) runs once per frame:
  st     : state dict (None = fresh), plain data only
  t      : seconds (absTime.seconds)
  inp    : {'value': audio channel value 0..1, 'key': 0/1, 'flash': bool, 'link_bpm': float or None}
  p      : params (see DEFAULTS)
  events : list of 'fire' / 'burst' / 'resync' pulses since the last step
returns (st, out) with out = {'env', 'lin', 'hit', 'count', 'beat', 'bpm', 'armed', 'hits'}.
"""
import math

SOURCES = ['kick', 'low', 'level', 'bpm', 'lfo', 'manual']
AUDIO_SOURCES = ('kick', 'low', 'level')
TEMPOS = ['project', 'manual', 'link', 'tap']
NOTES = ['bars4', 'bars2', 'bar1', 'n2', 'n4', 'n8', 'n16', 'n32']
NOTE_LABELS = ['4 bars', '2 bars', '1 bar', '1/2', '1/4', '1/8', '1/16', '1/32']
NOTE_BEATS = {'bars4': 16.0, 'bars2': 8.0, 'bar1': 4.0, 'n2': 2.0, 'n4': 1.0, 'n8': 0.5, 'n16': 0.25, 'n32': 0.125}
NOTEMODS = ['straight', 'triplet', 'dotted']
NOTEMOD_MUL = {'straight': 1.0, 'triplet': 2.0 / 3.0, 'dotted': 1.5}
EASES = ['linear', 'in', 'out', 'inout']
MODES = ['lift', 'dip', 'invert', 'colour']
DIVISIONS = ['1', '2', '4', '8', '16']
HYST = 0.15
EPS = 1e-9          # float slack on hit times (frame times are sums of 1/60)

DEFAULTS = {
    'source': 'kick', 'threshold': 0.6, 'division': 1, 'tempo': 'project', 'bpm': 120.0, 'project_bpm': 120.0,
    'note': 'n4', 'notemod': 'straight', 'phase': 0.0, 'swing': 0.0, 'rate': 2.0, 'burstcount': 4, 'hold': 0.0,
    'attack': 0.01, 'release': 0.15, 'depth': 1.0, 'ease': 'linear', 'blackout': False,
}


def note_beats(note, notemod='straight'):
    """Beats per hit for a Note menu entry and modifier (triplet x2/3, dotted x1.5)."""
    return NOTE_BEATS.get(note, 1.0) * NOTEMOD_MUL.get(notemod, 1.0)


def resolve_bpm(p, link_bpm=None):
    """Active tempo: project (TD timeline tempo), manual / tap (Bpm par), link (Link CHOP tempo, else project)."""
    tm = p.get('tempo', 'project')
    if tm in ('manual', 'tap'):
        return float(p.get('bpm', 120.0))
    if tm == 'link' and link_bpm is not None and link_bpm > 0:
        return float(link_bpm)
    return float(p.get('project_bpm', 120.0))


def ease(x, kind='linear'):
    """Envelope easing on 0..1."""
    x = 0.0 if x < 0 else (1.0 if x > 1 else x)
    if kind == 'in':
        return x * x
    if kind == 'out':
        return 1.0 - (1.0 - x) * (1.0 - x)
    if kind == 'inout':
        return x * x * (3.0 - 2.0 * x)
    return x


def envelope(elapsed, attack, release):
    """Linear flash shape: 0 -> 1 over attack s, then 1 -> 0 over release s. elapsed None = no flash yet."""
    if elapsed is None or elapsed < 0:
        return 0.0
    if attack > 0 and elapsed < attack:
        return elapsed / attack
    r = elapsed - max(attack, 0.0)
    if release <= 0:
        return 1.0 if r <= 0 else 0.0
    return max(0.0, 1.0 - r / release)


def tap_bpm(taps, now, max_gap=2.0, keep=4):
    """Tap tempo: add now to taps (a gap > max_gap starts over), keep the last `keep`+1 taps.
    Returns (taps, bpm or None). bpm = 60 / mean interval of the last `keep` intervals."""
    taps = [x for x in (taps or [])]
    if taps and (now - taps[-1] > max_gap or now <= taps[-1]):
        taps = []
    taps.append(now)
    taps = taps[-(keep + 1):]
    if len(taps) < 2:
        return taps, None
    iv = (taps[-1] - taps[0]) / (len(taps) - 1)
    return taps, (60.0 / iv if iv > 0 else None)


def bpm_hits(prev_pos, pos, beats_per_hit, phase=0.0, swing=0.0):
    """Number of hit times in (prev_pos, pos] on a beat axis. Hit k sits at (k + phase) * L, odd k delayed by
    swing * L. A frame that crosses several hits still flashes once (the caller only needs > 0)."""
    L = float(beats_per_hit)
    if L <= 0 or pos <= prev_pos:
        return 0
    n = 0
    k0 = int(math.floor(prev_pos / L - phase)) - 1
    k1 = int(math.floor(pos / L - phase)) + 1
    for k in range(k0, k1 + 1):
        tk = (k + phase) * L + (swing * L if (k % 2) else 0.0)
        if prev_pos + EPS < tk <= pos + EPS:
            n += 1
    return n


def new_state():
    return {'t': None, 'pos': 0.0, 'lfo': 0.0, 'armed': True, 'count': 0, 'last_hit': None, 'start': None,
            'held': False, 'key': 0, 'burst_left': 0, 'burst_next': 0.0, 'hits': 0}


def _get(p, k):
    return p[k] if k in p else DEFAULTS[k]


def step(st, t, inp, p, events=()):
    st = dict(st) if st else new_state()
    ev = list(events or ())
    t = float(t)
    dt = 0.0 if st['t'] is None else max(0.0, t - st['t'])
    st['t'] = t
    src = _get(p, 'source')
    bpm = resolve_bpm(p, inp.get('link_bpm'))
    beats = note_beats(_get(p, 'note'), _get(p, 'notemod'))
    hit_auto = False
    hit_manual = False

    # tempo clock always runs (Burst spacing and bpm mode use it)
    prev_pos = st['pos']
    st['pos'] = prev_pos + dt * bpm / 60.0
    if 'resync' in ev:
        st['pos'] = _get(p, 'phase') * beats
        prev_pos = st['pos'] - 1e-9
        if src == 'bpm':
            hit_auto = True

    if src in AUDIO_SOURCES:
        v = float(inp.get('value', 0.0))
        th = float(_get(p, 'threshold'))
        if st['armed'] and v >= th:
            st['armed'] = False
            st['count'] += 1
            div = max(1, int(_get(p, 'division')))
            if (st['count'] - 1) % div == 0:
                hit_auto = True
        elif not st['armed'] and v < th - HYST:
            st['armed'] = True
    elif src == 'bpm':
        if bpm_hits(prev_pos, st['pos'], beats, _get(p, 'phase'), _get(p, 'swing')) > 0:
            hit_auto = True
    elif src == 'lfo':
        st['lfo'] += dt * float(_get(p, 'rate'))
        if st['lfo'] >= 1.0 - EPS:
            st['lfo'] = max(0.0, st['lfo'] - int(st['lfo'] + EPS))
            hit_auto = True

    hold = float(_get(p, 'hold'))
    if hit_auto and hold > 0 and st['last_hit'] is not None and t - st['last_hit'] < hold - 1e-9:
        hit_auto = False

    # manual: Fire, Key (rising edge), Burst queue; never blocked by Hold
    if 'fire' in ev:
        hit_manual = True
    k = 1 if inp.get('key', 0) else 0
    if k and not st['key']:
        hit_manual = True
    st['key'] = k
    if 'burst' in ev:
        n = max(1, int(_get(p, 'burstcount')))
        hit_manual = True
        st['burst_left'] = n - 1
        st['burst_next'] = t + _burst_gap(src, p, bpm, beats)
    elif st['burst_left'] > 0 and t >= st['burst_next'] - 1e-9:
        hit_manual = True
        st['burst_left'] -= 1
        st['burst_next'] += _burst_gap(src, p, bpm, beats)

    hit = hit_auto or hit_manual
    attack, release = float(_get(p, 'attack')), float(_get(p, 'release'))
    if hit:
        st['last_hit'] = t
        # the hit sits at the start of this frame: an attack shorter than a frame peaks on the hit frame itself
        fdt = dt if dt > 0 else 1.0 / 60.0
        st['start'] = t - min(max(attack, 0.0), fdt)
        st['hits'] += 1

    flash = bool(inp.get('flash', False))
    if flash:
        lin = 1.0
        st['held'] = True
    else:
        if st['held'] and not hit:                 # released: decay from full now
            st['start'] = t - max(attack, 0.0)
        st['held'] = False
        lin = envelope(None if st['start'] is None else t - st['start'], attack, release)
    env = ease(lin, _get(p, 'ease')) * float(_get(p, 'depth'))
    out = {'env': env, 'lin': lin, 'hit': 1.0 if hit else 0.0, 'count': float(st['count']), 'beat': st['pos'],
           'bpm': bpm, 'armed': 1.0 if st['armed'] else 0.0, 'hits': float(st['hits'])}
    return st, out


def _burst_gap(src, p, bpm, beats):
    """Seconds between Burst hits: 1/Rate in lfo mode, else the Note length at the active tempo."""
    if src == 'lfo':
        r = float(_get(p, 'rate'))
        return 1.0 / r if r > 0 else 0.0
    return 60.0 / bpm * beats if bpm > 0 else 0.0
