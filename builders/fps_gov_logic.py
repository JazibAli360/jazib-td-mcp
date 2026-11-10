# fps_gov_logic - pure step / hysteresis logic of FG_fps_governor (no td). ASCII only.
# Copied into FG_fps_governor/fg_logic by builders/fps_gov.py; tests: test/test_fps_gov.py.
#
# One sample per frame: interval_ms (real time since the last frame start, the frame clock) and busy_ms (the frame's
# cook time, Perform CHOP msec; read every BUSY_EVERY frames, None in between). Both are smoothed (EMA).
# The governor holds a step 0..Steps:
#   quality = 1 - (1 - Floor) * step / Steps      (step 0 = 1.0 = full, step Steps = Floor)
#   too slow:   smoothed fps < Target * LOW_FRAC and headroom < Upmargin ms, Downafter frames in a row -> step + 1
#               (a drop while this TD's own frame cook is still cheap comes from outside: lowering quality would
#               not help, so it does not count)
#   keeping up: smoothed fps >= Target * HIGH_FRAC and headroom >= Upmargin ms: Upafter such frames, not
#               necessarily in a row; any too-slow frame restarts the count -> step - 1
#   in between: the down run breaks, the up count holds.
# After every step change the EMA re-seeds (the new load is measured fresh) and the counters restart.
# Anti-oscillation: a step-down within Upafter frames of a step-up doubles the next up wait (max BACKOFF_MAX x);
# a step-up that then holds for its whole wait resets it.

ALPHA = 0.1            # EMA weight of a new sample (~10-frame time constant)
LOW_FRAC = 0.95        # 60 fps target: < 57 fps smoothed = too slow
HIGH_FRAC = 0.985      # 60 fps target: >= 59.1 fps smoothed = keeping up
SAMPLE_CAP = 4.0       # one sample is clamped to 4 x the frame budget (a 2 s stall counts as slow, not as 2 s)
BACKOFF_MAX = 8
BUSY_EVERY = 4         # Perform CHOP read every N frames (its cook is most of the cost)
SHOW_EVERY = 30        # fps / headroom_ms outputs refresh every N frames (quality / step at once); every write
                       # re-cooks out1's consumers (a CHOP reference depends on the whole CHOP)


def cfg(target=60.0, downafter=30, upafter=300, steps=5, floor=0.25, upmargin=3.0):
    """Clamp raw par values into a config dict."""
    return {
        'target': min(max(float(target), 1.0), 1000.0),
        'downafter': max(int(downafter), 1),
        'upafter': max(int(upafter), 1),
        'steps': max(int(steps), 0),
        'floor': min(max(float(floor), 0.0), 1.0),
        'upmargin': max(float(upmargin), 0.0),
    }


def new_state():
    return {'step': 0, 'down': 0, 'up': 0, 'ema_int': None, 'ema_busy': None, 'backoff': 1,
            'since_up': None, 'frames': 0}


def quality(step, steps, floor):
    if steps <= 0:
        return 1.0
    s = min(max(int(step), 0), steps)
    return round(1.0 - (1.0 - floor) * s / float(steps), 4)


def _ema(prev, x):
    return x if prev is None else prev + ALPHA * (x - prev)


def _restart(st):
    st['down'] = 0
    st['up'] = 0
    st['ema_int'] = None
    st['ema_busy'] = None


def fps_of(st):
    e = st['ema_int']
    return 1000.0 / e if e else 0.0


def headroom_of(st, c):
    e = st['ema_busy']   # no busy sample yet = 0 headroom (never steps up blind)
    return (1000.0 / c['target'] - e) if e is not None else 0.0


def _shown(st, c):
    """fps / headroom for the outputs: the last measured values while the EMA re-seeds after a step change."""
    if st['ema_int'] is not None:
        st['fps_last'] = fps_of(st)
    if st['ema_busy'] is not None:
        st['head_last'] = headroom_of(st, c)
    return st.get('fps_last', 0.0), st.get('head_last', 0.0)


def up_wait(st, c):
    return c['upafter'] * st['backoff']


def tick(st, interval_ms, busy_ms, c):
    """Advance one frame. Returns +1 (stepped down in quality), -1 (stepped up) or 0."""
    st['frames'] += 1
    if st['step'] > c['steps']:            # Steps lowered live
        st['step'] = c['steps']
    budget = 1000.0 / c['target']
    cap = budget * SAMPLE_CAP
    iv = min(max(float(interval_ms), 0.0), cap)
    if iv <= 0.0:                          # no real interval (first frame, paused): ignore
        return 0
    st['ema_int'] = _ema(st['ema_int'], iv)
    if busy_ms is not None:                # busy may be sampled every few frames (None = not this frame)
        st['ema_busy'] = _ema(st['ema_busy'], min(max(float(busy_ms), 0.0), cap))
    if st['since_up'] is not None:
        st['since_up'] += 1
        if st['since_up'] > c['upafter']:   # the last step-up held for a whole base wait
            st['backoff'] = 1
            st['since_up'] = None
    fps = fps_of(st)
    head = headroom_of(st, c)
    if fps < c['target'] * LOW_FRAC and head < c['upmargin']:
        st['up'] = 0
        st['down'] += 1
        if st['down'] >= c['downafter'] and st['step'] < c['steps']:
            if st['since_up'] is not None and st['since_up'] <= c['upafter']:
                st['backoff'] = min(st['backoff'] * 2, BACKOFF_MAX)
            st['since_up'] = None
            st['step'] += 1
            _restart(st)
            return 1
        return 0
    if fps >= c['target'] * HIGH_FRAC and head >= c['upmargin']:
        st['down'] = 0
        st['up'] += 1
        if st['up'] >= up_wait(st, c) and st['step'] > 0:
            st['step'] -= 1
            st['since_up'] = 0
            _restart(st)
            return -1
        return 0
    st['down'] = 0
    return 0


def outputs(st, c):
    """The out1 channel values: quality, step, fps, headroom_ms."""
    fps, head = _shown(st, c)
    return {'quality': quality(st['step'], c['steps'], c['floor']), 'step': float(st['step']),
            'fps': round(fps, 1), 'headroom_ms': round(head, 2)}


# Recommended PX mapping (docs/builds/fps_governor.md): ordered thresholds on quality, cheapest visible loss first,
# on the same rungs as PX's own ladder (px_logic.aq_steps: splat MSAA 1x -> AQ_COUNTS 0.75 / 0.5 -> AQ_RES 0.75 /
# 0.5). With Steps 5 and Floor 0.25 the governor's qualities 1 / .85 / .7 / .55 / .4 / .25 land on one rung each.
PX_LEVELS = [
    (0.9, 'splat AA -> 1x'),
    (0.8, 'count fraction 0.75'),
    (0.65, 'count fraction 0.5'),
    (0.5, 'resolution fraction 0.75'),
    (0.35, 'resolution fraction 0.5'),
]


def px_plan(q):
    """PX at governor quality q, in px_logic.aq_effect's shape: (force splat AA 1x, count fraction, res fraction)."""
    return (q < 0.9,
            1.0 if q >= 0.8 else (0.75 if q >= 0.65 else 0.5),
            1.0 if q >= 0.5 else (0.75 if q >= 0.35 else 0.5))


# Runtime state per governor COMP path (module memory, never op storage; a text reload starts fresh).
STATES = {}


def state_for(key):
    st = STATES.get(key)
    if st is None:
        st = STATES[key] = new_state()
    return st
