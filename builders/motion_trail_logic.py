"""motion_trail logic: pure Python (no td), copied into FX_motion_trail/motion_trail_logic as a Text DAT module.

Trail model (docs/research/BA_motion_tracer.md section 5, our own clean-room design): every pixel keeps an age value
t in 0..1 (1 = moved this frame, 0 = gone). Motion (frame difference above Threshold) writes t = mask; otherwise
t drops by `step` = 1 / length_frames per frame, so a trail lives exactly `length` frames and t encodes age linearly
(colour-by-age is free: age = 1 - t). Opacity = t ** gamma, gamma from Decay (0 -> 0.25 hangs on, 0.5 -> 1 linear,
1 -> 4 fades fast). Palette mode: age -> position in a palette (FX_palette_map's presets / custom table / file, same
palette_map_logic module copied in), Spread = palette (or hue) cycles over a trail's life, Cycle = cycles per second.
Pure ASCII.
"""
import math

QUALITY = (('full', 'Full res'), ('half', 'Half res'), ('quarter', 'Quarter res'))
QUALITY_SCALE = {'full': 1.0, 'half': 0.5, 'quarter': 0.25}
AGECOLOR = (('ramp', 'Ramp (new -> mid -> old)'), ('white', 'White only'), ('source', 'Source colour (captured)'),
            ('palette', 'Palette by age'), ('rainbow', 'Rainbow cycle (hue by age + time)'))
BLEND = (('over', 'Over source'), ('add', 'Add'), ('screen', 'Screen'), ('trail', 'Trail only (premultiplied alpha)'))
LENGTHUNIT = (('frames', 'Frames'), ('beats', 'Beats (BPM)'))


def menu_index(menu, name, default=0):
    for k, (n, _label) in enumerate(menu):
        if n == name:
            return k
    return default


def length_frames(length, unit='frames', beats=1.0, bpm=120.0, fps=60.0):
    """Trail life in project frames. Beats mode: beats * 60 / bpm seconds at fps. Never below 1 frame."""
    if unit == 'beats':
        bpm = max(float(bpm), 1e-6)
        n = float(beats) * 60.0 / bpm * float(fps)
    else:
        n = float(length)
    return max(1.0, n)


def step(length, unit='frames', beats=1.0, bpm=120.0, fps=60.0):
    """Age decrement per frame (shader uniform)."""
    return 1.0 / length_frames(length, unit, beats, bpm, fps)


def gamma(decay):
    """Decay 0..1 -> opacity exponent 2 ** (4 * decay - 2): 0 -> 0.25, 0.5 -> 1.0, 1 -> 4.0 (unclamped beyond)."""
    return 2.0 ** (4.0 * float(decay) - 2.0)


def work_size(w, h, quality):
    """Working (trail) resolution for a source size; even, at least 2 px."""
    s = QUALITY_SCALE.get(quality, 1.0)

    def ev(v):
        return max(2, int(round(v * s / 2.0)) * 2)
    return ev(w), ev(h)


def palette_pos(t, spread=1.0, phase=0.0):
    """Position 0..1 along the palette / hue wheel for age value t (1 fresh .. 0 old).
    No cycling (spread <= 1, phase 0): clamped (first colour = newest, last = oldest); else wraps."""
    k = 1.0 - min(max(float(t), 0.0), 1.0)
    p = k * float(spread) + float(phase)
    if float(spread) <= 1.0 and float(phase) == 0.0:
        return min(max(p, 0.0), 1.0)
    return p - math.floor(p)


def cycle_phase(seconds, speed):
    """Time offset (cycles, wrapped 0..1) for Cycle = cycles per second."""
    v = float(seconds) * float(speed)
    return v - math.floor(v)


def palette_color(pos, cols, smooth=True):
    """Colour at position 0..1 over a list of rgb tuples: smooth = blend neighbours, else hard bands."""
    n = len(cols)
    if n == 0:
        return (0.0, 0.0, 0.0)
    if n == 1:
        return tuple(cols[0])
    if not smooth:
        i = min(int(pos * n), n - 1)
        return tuple(cols[i])
    x = min(max(pos, 0.0), 1.0) * (n - 1)
    i = min(int(math.floor(x)), n - 2)
    u = x - i
    a, b = cols[i], cols[i + 1]
    return tuple(a[j] + (b[j] - a[j]) * u for j in range(3))


def hue_rgb(h):
    """Full-saturation, full-value hue h (cycles) -> rgb (same as the shader's clamp(abs(fract(h+k)*6-3)-1))."""
    h = h - math.floor(h)
    out = []
    for k in (0.0, 2.0 / 3.0, 1.0 / 3.0):
        f = (h + k) - math.floor(h + k)
        out.append(min(max(abs(f * 6.0 - 3.0) - 1.0, 0.0), 1.0))
    return tuple(out)


def mix_amount(mix, audio_amount=0.0, level=None):
    """Trail opacity: Mix, scaled by an optional audio level (0..1) when Audioamount > 0.
    amount 0 -> Mix; amount 1 -> Mix * level. No level connected -> Mix."""
    if level is None:
        return float(mix)
    a = float(audio_amount)
    return float(mix) * (1.0 - a + a * float(level))


def reset_now(frame, clear_frame, clip_index=None, reset_on_loop=True, source='clip'):
    """1 while the trail must be cleared: 2 frames after a Clear pulse, or at the clip's loop point (index < 1)."""
    if 0 <= frame - clear_frame < 2:              # a Clear stored by another session (later frame) is no Clear
        return 1
    if reset_on_loop and source == 'clip' and clip_index is not None and clip_index < 1.0:
        return 1
    return 0


# --- reference model of the shaders (offline tests check the GPU numbers against this) ---

def mask(diff, threshold, softness):
    """smoothstep(threshold, threshold + softness, diff) like GLSL."""
    e0 = float(threshold)
    e1 = e0 + max(float(softness), 1e-4)
    x = min(max((diff - e0) / (e1 - e0), 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def trail_update(age, col, diff, src_col, threshold, softness, stp, hold=False, reset=False):
    """One frame of the trail pass for one pixel: returns (new_age, new_col)."""
    if reset:
        return 0.0, (0.0, 0.0, 0.0)
    m = mask(diff, threshold, softness)
    a = age if hold else max(age - stp, 0.0)
    if m >= a and m > 0.0:
        return m, tuple(src_col)
    return a, tuple(col)


def ramp(t, new, mid, old):
    """Colour for age value t (1 fresh .. 0 old): new -> mid -> old."""
    k = 1.0 - min(max(t, 0.0), 1.0)
    if k < 0.5:
        u, a, b = k * 2.0, new, mid
    else:
        u, a, b = k * 2.0 - 1.0, mid, old
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))


def shade(src, t, trail_col, mode, blend, mix, gam, new, mid, old, srclevel=1.0, pal=None, smooth=True,
          spread=1.0, phase=0.0):
    """Output pixel (r, g, b, a) of the look pass. pal = rgb list (palette mode)."""
    a = (max(t, 0.0) ** gam) * mix if t > 0 else 0.0
    if mode == 'white':
        rc = (1.0, 1.0, 1.0)
    elif mode == 'source':
        rc = tuple(trail_col)
    elif mode == 'palette':
        rc = palette_color(palette_pos(t, spread, phase), pal or [], smooth)
    elif mode == 'rainbow':
        rc = hue_rgb((1.0 - min(max(t, 0.0), 1.0)) * float(spread) + float(phase))   # hue wraps by itself
    else:
        rc = ramp(t, new, mid, old)
    s = tuple(c * srclevel for c in src[:3])
    sa = src[3] if len(src) > 3 else 1.0
    if blend == 'add':
        o = tuple(s[i] + rc[i] * a for i in range(3))
        return o + (max(sa, a),)
    if blend == 'screen':
        o = tuple(1.0 - (1.0 - s[i]) * (1.0 - rc[i] * a) for i in range(3))
        return o + (max(sa, a),)
    if blend == 'trail':
        return tuple(rc[i] * a for i in range(3)) + (a,)
    o = tuple(s[i] + (rc[i] - s[i]) * a for i in range(3))
    return o + (max(sa, a),)
