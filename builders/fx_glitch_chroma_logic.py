# fx_glitch_chroma_logic - numpy mirror of FX_glitch 'chroma' Split time (TC-26) with Distance 0: channel c of out1 =
# the frame (order slot of c) x Delay cooks back, clamped to the cooks the ring holds (stamp z). For the live check:
# feed a cook-counter probe (every channel = the counter), then out - in per channel decodes the offsets. Pure numpy.
import numpy as np

ORDERS = ['rgb', 'rbg', 'grb', 'gbr', 'brg', 'bgr']


def slots(order):
    o = ORDERS[order] if isinstance(order, int) else order
    return [o.index(ch) for ch in 'rgb']


def offsets(delay, order, n):
    """cooks back per channel R G B for Delay, Order and n cooks since the ring restarted."""
    D = 2 * int(delay)                                     # Depth - 1
    return [min(max(k * int(delay), 0), min(D, int(n))) for k in slots(order)]


def reference(frames, delay, order, n, amount=1.0):
    """frames: list of [H, W, 4] arrays, frames[-1] = now. -> out1 for Split time, Distance 0."""
    now = np.asarray(frames[-1], dtype=np.float64)
    out = now.copy()
    for ch, off in enumerate(offsets(delay, order, n)):
        src = np.asarray(frames[-1 - off], dtype=np.float64)
        out[..., ch] = now[..., ch] + (src[..., ch] - now[..., ch]) * amount
    return out


def decode(in_counter, out_rgb):
    """Probe: in = counter value (any channel), out channels -> cooks back per channel (rounded)."""
    return [int(round(float(in_counter) - float(v))) for v in out_rgb]
