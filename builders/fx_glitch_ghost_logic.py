# fx_glitch_ghost_logic - numpy mirror of the FX_glitch 'ghost' state pass (builders/fx_glitch_ghost.py).
# Pure numpy, exec-able inside TD for live parity. Arrays [y, x, rgba] in TD's TOP readback layout (row 0 = bottom),
# float 0..1. State = dict(prev, trail, plate) arrays; stamp = (now, previous cook, last capture). ASCII only.
import numpy as np

DEFAULTS = {'Amount': 1.0, 'Mode': 0, 'View': 0, 'Diff': 0, 'Threshold': 0.08, 'Softness': 0.05, 'Gain': 1.0,
            'Decay': 0.9, 'Capture': 0.0, 'Back': 0, 'Backdim': 0.25, 'Glowgain': 1.0, 'Tintr': 0.3, 'Tintg': 0.9,
            'Tintb': 1.0}
LUMA = np.array([0.2126, 0.7152, 0.0722])


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def step(c, state, pars=None, stamp=(1.0, 0.0, 1.0)):
    """One state cook. c = picture; state = {'prev', 'trail', 'plate'} or None (fresh); stamp = (now, prev cook,
    capture time). Returns (out, new_state). out is the b0 buffer before the 16F store."""
    P = pars_of(pars)
    c = np.asarray(c, dtype=np.float64)
    now, pc, ct = stamp
    fresh = state is None or pc <= 0.0 or now - pc > 0.25
    grab = ct == now
    prev = c if fresh else state['prev']
    trail = np.zeros_like(c) if fresh else state['trail']
    plate = c if (grab or state is None) else state['plate']
    dt = 0.0 if fresh else min(max(now - pc, 0.0), 0.1)
    mode = int(P['Mode'])
    ref = plate[..., :3] if mode == 3 else prev[..., :3]
    if int(P['Diff']) == 0:
        d = np.abs(c[..., :3] - ref).max(-1)
    else:
        d = np.abs(c[..., :3] @ LUMA - ref @ LUMA)
    m = smoothstep(P['Threshold'], P['Threshold'] + max(P['Softness'], 1e-5), d * P['Gain'])
    k = max(P['Decay'], 0.0) ** (dt * 60.0) if dt > 0.0 else 1.0
    trail = np.concatenate([np.maximum(trail[..., :3] * k, c[..., :3] * m[..., None]),
                            np.maximum(trail[..., 3:] * k, m[..., None])], -1)
    bm = int(P['Back'])
    if bm == 0:
        back = np.concatenate([np.zeros_like(c[..., :3]), c[..., 3:]], -1)
    elif bm == 1:
        back = np.concatenate([c[..., :3] * P['Backdim'], c[..., 3:]], -1)
    else:
        back = np.zeros_like(c)
    if mode == 1:
        tint = np.array([P['Tintr'], P['Tintg'], P['Tintb']])
        o = np.concatenate([c[..., :3] + tint * P['Glowgain'] * trail[..., 3:], c[..., 3:]], -1)
    elif mode == 2:
        o = np.maximum(back, trail)
    else:
        o = back + (c - back) * m[..., None]
    if int(P['View']) == 1:
        v = trail[..., 3] if mode in (1, 2) else m
        o = np.concatenate([np.repeat(v[..., None], 3, -1), np.ones_like(v[..., None])], -1)
    out = c + (o - c) * P['Amount']
    return out, {'prev': c, 'trail': trail, 'plate': plate}


def f16(a):
    """Round like the rgba16float store."""
    return np.asarray(a, dtype=np.float16).astype(np.float64)


def compare(td_out, ref, tol=2e-3):
    a = np.asarray(td_out, dtype=np.float64)
    b = np.asarray(ref, dtype=np.float64)
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'over': float((d > tol).mean())}
