# fx_scope_logic - FX_scope pure maths + numpy references (no `td`). Used by the offline tests, by the LIVE CHECK
# snippets (save GPU readbacks, compare here) and by the module builders for constants and par-expression lambdas.
# Modules: xy, vector, lissajous (shared beam engine builders/fx_scope_beam.py), scopes, hud. Doc: docs/builds/fx_scope.md.
# Conventions (= TD texel space): image arrays are [row, col] with row 0 = the BOTTOM texel row (numpyArray order),
# pixel centres at (i + 0.5, j + 0.5), y up. ASCII only.
import json
import math
import os

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

# ------------------------------------------------------------------ path / beam geometry (mirrors fx_scope_lib.glsl)
CAP = 16384                 # points per frame (path texture 1024 x 16 + 1 bbox row)
ROWW = 1024
CAPROW = CAP // ROWW        # 16: row of the chunk bboxes + count texel
CH = 256                    # segments per chunk (= beam workgroup size)
NCH = CAP // CH             # 64 chunks
PATH_WH = (ROWW, CAPROW + 1)
TILE = 32                   # beam tile (16x16 threads x 2x2 px)
CUT = 5.0                   # beam cut radius in sigmas (energy beyond: e^-12.5 = 3.7e-6 of the peak)
SQ2PI = math.sqrt(2.0 * math.pi)
LUMA709 = (0.2126, 0.7152, 0.0722)
LUMA601 = (0.299, 0.587, 0.114)
QUALITIES = ['full', 'half', 'quarter']
QUALITY = {'full': 1.0, 'half': 0.5, 'quarter': 0.25}
Q_EXPR = "[1.0, 0.5, 0.25][parent().par.Quality.menuIndex]"

# Phosphors: key, label, afterglow tint (state), flash tint (current beam), tau multipliers r g b, mono.
PHOSPHORS = [
    ('p1', 'P1 green (classic scope)', (0.20, 1.0, 0.25), (0.55, 1.0, 0.60), (1.0, 1.0, 1.0), 1),
    ('p31', 'P31 green-blue (short)', (0.30, 1.0, 0.55), (0.75, 1.0, 0.85), (1.0, 1.0, 1.0), 1),
    ('p7', 'P7 blue flash, yellow afterglow (radar)', (0.80, 1.0, 0.20), (0.45, 0.65, 1.0), (1.0, 1.0, 0.35), 1),
    ('p4', 'P4 white (TV, Vectrex)', (0.92, 0.95, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), 1),
    ('p3', 'P3 amber', (1.0, 0.62, 0.12), (1.0, 0.80, 0.45), (1.0, 1.0, 1.0), 1),
    ('source', 'Source colours (RGB)', (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), 0),
    ('custom', 'Custom tint (Tint r g b)', None, None, (1.0, 1.0, 1.0), 1),
]
PHOSPHOR_NAMES = [p[0] for p in PHOSPHORS]
PHOSPHOR_LABELS = [p[1] for p in PHOSPHORS]

# par-expression lambdas (TD evaluates them; tests eval the same strings)
PANEL_LAMBDA = ("(lambda W, H, s, a, cx, cy: (lambda pw, ph: (cx * W - pw / 2.0, cy * H - ph / 2.0, pw, ph))("
                "s * (min(W, H) if a == 0 else W), s * (min(W, H) if a == 0 else H)))")
BEAMWH_LAMBDA = "(lambda pw, ph, q: (max(32, int(round(pw * q))), max(32, int(round(ph * q)))))"


def panel(W, H, size, aspect, cx, cy):
    """Scope panel in output px: (x0, y0, pw, ph). aspect 0 = square (side = size x min(W, H)), 1 = fill canvas."""
    return eval(PANEL_LAMBDA)(W, H, size, aspect, cx, cy)


def beam_wh(pw, ph, q):
    return eval(BEAMWH_LAMBDA)(pw, ph, q)


def beam_consts(bw, bh, beamwidth, q, fill=False):
    """-> sigma (buffer px), Kn, Lref, sx, sy (buffer px per unit). Intensity 1 = a line one Lref long drawn once per
    frame peaks at 1.0 (any beam width, any Quality); Kn = total energy per frame."""
    sigma = max(0.35, beamwidth * q)
    lref = float(min(bw, bh))
    sx, sy = ((bw / 2.0, bh / 2.0) if fill else (lref / 2.0, lref / 2.0))
    return sigma, lref * SQ2PI * sigma, lref, sx, sy


def erf_as(x):
    """Abramowitz-Stegun 7.1.26 (|error| < 1.5e-7), the shader's erfA. numpy or float."""
    if np is not None and isinstance(x, np.ndarray):
        s = np.sign(x)
        a = np.abs(x)
    else:
        s = math.copysign(1.0, x) if x != 0 else 0.0
        a = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    poly = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
    e = np.exp(-a * a) if (np is not None and isinstance(a, np.ndarray)) else math.exp(-a * a)
    return s * (1.0 - poly * e)


def pack_rgb(c):
    q = [int(min(max(v, 0.0), 1.0) * 255.0 + 0.5) for v in c]
    return float((q[0] << 16) | (q[1] << 8) | q[2])


def unpack_rgb(f):
    u = int(f + 0.5)
    return ((u >> 16) & 255) / 255.0, ((u >> 8) & 255) / 255.0, (u & 255) / 255.0


def place(units, bw, bh, sx, sy, rot_deg=0.0):
    """Path points in scope units (+-1) -> beam-buffer px (rotation about the centre, then scale)."""
    u = np.asarray(units, float).reshape(-1, 2)
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    x = u[:, 0] * c - u[:, 1] * s
    y = u[:, 0] * s + u[:, 1] * c
    return np.stack([0.5 * bw + x * sx, 0.5 * bh + y * sy], 1)


def splat_ref(P, w, col, bw, bh, sigma, kn, dwell, lref, intensity=1.0, mono=True):
    """Beam energy image E (bh, bw, 3) of the polyline P (n, 2 buffer px). w[j] = weight of segment j -> j+1 (0 =
    blank; w[n-1] unused), col[j] its rgb. Exactly the beam shader: per pixel, every segment whose capsule (radius
    CUT sigma) holds the pixel centre adds Kn I w [dwell dt G/L + (1 - dwell) G / Lref], G = the 2D Gaussian
    integrated along the segment (erf form), dt = 1/(n-1); point form (midpoint) below L 0.02 px."""
    P = np.asarray(P, float)
    n = len(P)
    E = np.zeros((bh, bw, 3))
    if n < 2:
        return E
    w = np.asarray(w, float)
    col = np.asarray(col, float).reshape(-1, 3)
    if mono:
        col = np.repeat((col @ np.asarray(LUMA709))[:, None], 3, 1)
    dt = 1.0 / (n - 1)
    wd, wu = intensity * kn * dwell * dt, intensity * kn * (1.0 - dwell) / max(lref, 1.0)
    R = CUT * sigma
    i2s2, is2, iq, i2p = 0.5 / sigma ** 2, 1.0 / (math.sqrt(2.0) * sigma), 1.0 / (SQ2PI * sigma), \
        1.0 / (2.0 * math.pi * sigma ** 2)
    for j in range(n - 1):
        if w[j] <= 0:
            continue
        a, b = P[j], P[j + 1]
        L = float(np.hypot(*(b - a)))
        u = (b - a) / L if L > 0 else np.array([1.0, 0.0])
        x0 = max(0, int(math.floor(min(a[0], b[0]) - R - 1)))
        x1 = min(bw, int(math.ceil(max(a[0], b[0]) + R + 1)))
        y0 = max(0, int(math.floor(min(a[1], b[1]) - R - 1)))
        y1 = min(bh, int(math.ceil(max(a[1], b[1]) + R + 1)))
        if x0 >= x1 or y0 >= y1:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        dx, dy = xx + 0.5 - a[0], yy + 0.5 - a[1]
        t = dx * u[0] + dy * u[1]
        tc = np.clip(t, 0.0, L)
        rx, ry = dx - u[0] * tc, dy - u[1] * tc
        inside = rx * rx + ry * ry <= R * R
        pp = dx * u[1] - dy * u[0]
        if L < 0.02:                                       # point form about the midpoint: error O(L^2 / s^2)
            tm = t - 0.5 * L
            g2 = np.exp(-(pp * pp + tm * tm) * i2s2) * i2p
            v = w[j] * wd * g2 + w[j] * wu * L * g2
        else:
            G = np.exp(-pp * pp * i2s2) * iq * 0.5 * (erf_as((L - t) * is2) + erf_as(t * is2))
            v = w[j] * wd * G / L + w[j] * wu * G
        v = np.where(inside, v, 0.0)
        E[y0:y1, x0:x1] += v[..., None] * col[j][None, None, :]
    return E


def capsule_in_bbox(a, b, R, p):
    """True when pixel centre p is within R of segment ab. The beam's tile cull uses the segment bbox grown by R: a
    capsule point always lies inside it (tests check this property, so culling never drops a contribution)."""
    a, b, p = (np.asarray(v, float) for v in (a, b, p))
    d = b - a
    L2 = float(d @ d)
    t = 0.0 if L2 == 0 else min(max(float((p - a) @ d) / L2, 0.0), 1.0)
    return float(np.hypot(*(p - (a + d * t)))) <= R


def phosphor_tints(key, tint=(1.0, 1.0, 1.0)):
    for k, _l, A, F, m, mono in PHOSPHORS:
        if k == key:
            if A is None:
                A = tuple(tint)
                F = tuple(0.5 + 0.5 * v for v in tint)
            return A, F, m, mono
    raise KeyError(key)


def phosphor_step(S_prev, E, A, tau, dt_s, reset=False):
    """State update of the beam pass: S = S_prev exp(-dt/tau_c) (tau <= 0: no persistence) + E * A; alpha = luma(E)."""
    S = np.zeros_like(E) if (reset or S_prev is None) else S_prev * np.array(
        [math.exp(-dt_s / t) if t > 0 else 0.0 for t in tau])[None, None, :]
    S = S + E * np.asarray(A)[None, None, :]
    alpha = E @ np.asarray(LUMA709)
    return S, alpha


def tonemap(x, exposure=1.0):
    return 1.0 - np.exp(-exposure * np.asarray(x))


# ------------------------------------------------------------------ path sources (mirror the src_*.glsl files)
def catmull(p0, p1, p2, p3, f):
    f2, f3 = f * f, f * f * f
    return 0.5 * (2 * p1 + (p2 - p0) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f2 + (3 * p1 - p0 - 3 * p2 + p3) * f3)


def audio_count(n, k):
    return 0 if n < 2 else min(CAP, (n - 1) * max(int(k), 1) + 1)


def audio_points(samples, k):
    """N samples (N, 2) -> np points: point j sits at sample-space s = j (N-1)/(np-1), Catmull-Rom, ends clamped.
    Oversamples (K) or decimates (N > CAP) with the same rule (fx_scope_audio.glsl)."""
    S = np.asarray(samples, float).reshape(-1, 2)
    n = len(S)
    m = audio_count(n, k)
    out = np.zeros((m, 2))
    for j in range(m):
        s = j * (n - 1) / float(max(m - 1, 1))
        i = int(math.floor(s))
        f = s - i
        if i >= n - 1:
            i, f = n - 2, 1.0
        q = [S[min(max(i + d, 0), n - 1)] for d in (-1, 0, 1, 2)]
        out[j] = catmull(q[0], q[1], q[2], q[3], f)
    return out


def test_tone(n, fx, fy, phx, phy, amp):
    """The xy / goniometer test source: n samples, x = amp sin 2pi(phx + fx i), y = amp sin 2pi(phy + fy i);
    fx, fy in cycles per sample, phases in cycles (the frame's start phase, kept continuous by the uniforms)."""
    i = np.arange(n, dtype=float)
    return np.stack([amp * np.sin(2 * math.pi * (phx + fx * i)), amp * np.sin(2 * math.pi * (phy + fy * i))], 1)


def test_tone_uniforms(freq, ratio, phase_deg, amp, rate, frame, cookrate):
    """-> (fx, fy, phx, phy, n) as the uniforms set them: n = round(rate / cookRate) samples per frame; the start
    phases advance with absTime.frame so the tone runs on from frame to frame."""
    n = int(round(rate / max(cookrate, 1.0)))
    fx, fy = freq / rate, freq * ratio / rate
    phx = (freq * frame / cookrate) % 1.0
    phy = (freq * ratio * frame / cookrate + phase_deg / 360.0) % 1.0
    return fx, fy, phx, phy, n


FIGURES = ['lissajous', 'harmonograph', 'spirograph', 'rose', 'goniometer']


def spiro_period(R, r, turns=1.0):
    """Hypotrochoid closes after r / gcd(R, r) turns of the wheel (integers; others: one turn x r)."""
    Ri, ri = int(round(R)), int(round(r))
    if abs(R - Ri) < 1e-9 and abs(r - ri) < 1e-9 and ri > 0:
        return 2 * math.pi * ri / math.gcd(Ri, ri) * turns
    return 2 * math.pi * max(r, 1e-6) * turns


def rose_period(n, d, turns=1.0):
    """r = cos(n/d theta) closes after pi d (n d odd) or 2 pi d (integers)."""
    ni, di = int(round(n)), max(int(round(d)), 1)
    return (math.pi * di if (ni * di) % 2 == 1 else 2 * math.pi * di) * turns


def hsv2rgb(h, s=1.0, v=1.0):
    h = np.asarray(h, float) % 1.0
    k = (np.array([5.0, 3.0, 1.0])[None, :] + h.reshape(-1, 1) * 6.0) % 6.0
    return v - v * s * np.clip(np.minimum(k, 4.0 - k), 0.0, 1.0)


def figure_points(fig, np_, a=3.0, b=2.0, phase=0.25, drift=0.0, turns=1.0, damping=0.0, c=2.0, d=3.0, mix=0.0,
                  start=0.0, length=1.0, R=5.0, r=3.0, pen=5.0, rosek=1.0, period=None, gain=1.0, rainbow=False,
                  hue=0.0):
    """lissajous / harmonograph / spirograph / rose: np_ points in units + colours (fx_scope_src_lissajous.glsl)."""
    u = np.arange(np_, dtype=float) / max(np_ - 1, 1)
    tp = 2 * math.pi
    if fig == 'lissajous':
        th = tp * turns * u
        x, y = np.sin(a * th + tp * (phase + drift)), np.sin(b * th)
    elif fig == 'harmonograph':
        t = start + u * length
        dm = np.exp(-damping * t)
        x = dm * ((1 - mix) * np.sin(tp * (a * t + phase + drift)) + mix * np.sin(tp * c * t))
        y = dm * ((1 - mix) * np.sin(tp * b * t) + mix * np.sin(tp * (d * t + 0.25)))
    elif fig == 'spirograph':
        th = (period if period is not None else spiro_period(R, r, turns)) * u
        k = (R - r) / max(r, 1e-6)
        sc = 1.0 / max(abs(R - r) + abs(pen), 1e-6)
        x0 = ((R - r) * np.cos(th) + pen * np.cos(k * th)) * sc
        y0 = ((R - r) * np.sin(th) - pen * np.sin(k * th)) * sc
        ca, sa = math.cos(tp * drift), math.sin(tp * drift)
        x, y = x0 * ca - y0 * sa, x0 * sa + y0 * ca
    elif fig == 'rose':
        th = (period if period is not None else tp) * u
        rr = np.cos(rosek * th + tp * drift)
        x, y = rr * np.cos(th), rr * np.sin(th)
    else:
        raise ValueError(fig)
    col = hsv2rgb(u + hue) if rainbow else np.ones((np_, 3))
    return np.stack([x, y], 1) * gain, col


def goniometer(L, R):
    """M/S: x = (L - R)/sqrt2 (side), y = (L + R)/sqrt2 (mid): mono = a vertical line."""
    return (L - R) / math.sqrt(2.0), (L + R) / math.sqrt(2.0)


def correlation(L, R):
    L, R = np.asarray(L, float), np.asarray(R, float)
    den = math.sqrt(float((L * L).sum() * (R * R).sum()))
    return float((L * R).sum() / den) if den > 1e-12 else 0.0


# expression for the goniometer meter uniform (CHOP src_xy has the two channels in order)
CORR_EXPR = ("(lambda a: float((a[0] * a[1]).sum() / max(1e-12, float(((a[0] ** 2).sum() * (a[1] ** 2).sum()) ** 0.5)))"
             " if a is not None and len(a) >= 2 else 0.0)(op('src_xy').numpyArray() if op('src_xy').numChans >= 2 "
             "else None)")


def vector_path(xy, rgb, thr=0.02, colour=True, overshoot=0.0, flick=1.0):
    """Laser / CHOP stream -> points + segment weights + colours (fx_scope_src_vector.glsl): segment j lit by
    sample j+1's colour (the beam's colour when it lands), weight = its max channel x flicker."""
    xy = np.asarray(xy, float).reshape(-1, 2)
    rgb = np.asarray(rgb, float).reshape(-1, 3)
    n = min(len(xy), CAP)
    if len(xy) > CAP:
        idx = np.floor(np.arange(n) * (len(xy) - 1) / (n - 1) + 0.5).astype(int)
        xy, rgb = xy[idx], rgb[idx]
    p = xy[:n].copy()
    if overshoot:
        q = p.copy()
        q[1:-1] += overshoot * (2 * p[1:-1] - p[:-2] - p[2:])
        p = q
    nxt = np.minimum(np.arange(n) + 1, n - 1)
    c = rgb[nxt]
    lit = c.max(1)
    if colour:
        w = np.where(lit > thr, lit * flick, 0.0)
        col = np.clip(c / np.maximum(lit, 1e-6)[:, None], 0, 1)
    else:
        w = np.full(n, flick)
        col = np.ones((n, 3))
    return p, w, col


# ------------------------------------------------------------------ video scopes (fx_scope_hist.glsl)
SCOPES = ['waveform', 'parade', 'vectorscope', 'histogram']
LEVELS = [128, 256, 512]
BINS = [128, 256, 512]
GEOM_LAMBDA = ("(lambda m, W, H, st, lv, B: (lambda Sx, Sy, c: [(Sx, Sy, Sx, lv, (Sx + c - 1) // c, 1, c), "
               "(Sx, Sy, 3 * Sx, lv, 3 * ((Sx + c - 1) // c), 1, c), (Sx, Sy, B, B, B // 32, B // 32, 32), "
               "(Sx, Sy, lv, 4, 1, 4, lv)][m])((W + st - 1) // st, (H + st - 1) // st, 1024 // lv))")
GEOM_KEYS = ['Sx', 'Sy', 'w', 'h', 'gx', 'gy', 'cpt']


def hist_geom(mode, W, H, step, lv, B):
    """-> dict Sx Sy (sample grid), w h (bins texture), gx gy (workgroups), cpt (sample columns per tile)."""
    return dict(zip(GEOM_KEYS, eval(GEOM_LAMBDA)(SCOPES.index(mode) if isinstance(mode, str) else mode,
                                                 W, H, max(int(step), 1), lv, B)))


def sample_grid(img, step):
    """Sampled pixels the hist pass reads: (sx, sy) -> texel min(size-1, s step + step // 2). Returns (Sy, Sx, 3)."""
    H, W = img.shape[:2]
    Sx, Sy = (W + step - 1) // step, (H + step - 1) // step
    xs = np.minimum(np.arange(Sx) * step + step // 2, W - 1)
    ys = np.minimum(np.arange(Sy) * step + step // 2, H - 1)
    return np.clip(img[ys][:, xs, :3], 0.0, 1.0)


def ycbcr(rgb, matrix=0):
    kr, kg, kb = LUMA709 if matrix == 0 else LUMA601
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = kr * r + kg * g + kb * b
    return y, (b - y) / (2 * (1 - kb)), (r - y) / (2 * (1 - kr))


def level_bin(v, lv):
    return np.clip(np.floor(v * lv), 0, lv - 1).astype(int)


def hist_ref(img, mode, step=4, lv=256, B=256, matrix=0):
    """Bins texture as the hist pass writes it: counts[row, col] (row = texture y). waveform (lv, Sx): luma level by
    sample column; parade (lv, 3 Sx): R | G | B panels; vectorscope (B, B): col = Cb bin, row = Cr bin over +-0.5;
    histogram (4, lv): rows R G B luma."""
    s = sample_grid(img, step)
    Sy, Sx = s.shape[:2]
    y, cb, cr = ycbcr(s, matrix)
    if mode == 'waveform':
        out = np.zeros((lv, Sx), int)
        lb = level_bin(y, lv)
        for x in range(Sx):
            np.add.at(out[:, x], lb[:, x], 1)
    elif mode == 'parade':
        out = np.zeros((lv, 3 * Sx), int)
        for c in range(3):
            lb = level_bin(s[..., c], lv)
            for x in range(Sx):
                np.add.at(out[:, c * Sx + x], lb[:, x], 1)
    elif mode == 'vectorscope':
        out = np.zeros((B, B), int)
        bx = level_bin(cb + 0.5, B)
        by = level_bin(cr + 0.5, B)
        np.add.at(out, (by.ravel(), bx.ravel()), 1)
    elif mode == 'histogram':
        out = np.zeros((4, lv), int)
        for c, v in enumerate((s[..., 0], s[..., 1], s[..., 2], y)):
            np.add.at(out[c], level_bin(v, lv).ravel(), 1)
    else:
        raise ValueError(mode)
    return out


def bar_targets(matrix=0, amp=0.75):
    """Vectorscope colour-bar targets (Cb, Cr) for R Yl G Cy B Mg at `amp` (75 % or 100 % bars)."""
    cols = {'R': (1, 0, 0), 'Yl': (1, 1, 0), 'G': (0, 1, 0), 'Cy': (0, 1, 1), 'B': (0, 0, 1), 'Mg': (1, 0, 1)}
    out = {}
    for k, c in cols.items():
        _y, cb, cr = ycbcr(np.asarray(c, float)[None, :] * amp, matrix)
        out[k] = (float(cb[0]), float(cr[0]))
    return out


SKIN_DEG = 123.0            # skin-tone (I) line in the Cb/Cr plane, deg from +Cb

# ------------------------------------------------------------------ HUD (fx_scope_hud.glsl)
# False colour: (lo, hi, rgb or None = keep luma grey). 'arri'-style exposure bands of our own (signal 0..1).
FC_BANDS = [(0.0, 0.025, (0.5, 0.0, 0.6)), (0.025, 0.04, (0.0, 0.2, 1.0)), (0.38, 0.42, (0.1, 0.85, 0.2)),
            (0.52, 0.56, (1.0, 0.55, 0.7)), (0.97, 0.99, (1.0, 0.9, 0.0)), (0.99, 10.0, (1.0, 0.0, 0.0))]
FALSECOLOURS = ['exposure', 'spectrum', 'zones', 'clip']


def falsecolour(y, mode='exposure'):
    """Luma -> rgb (numpy). exposure = FC_BANDS over grey; spectrum = blue-cyan-green-yellow-red ramp; zones = 11
    stepped greys (Ansel Adams 0..X); clip = grey with red >= 0.99 and blue <= 0.02."""
    y = np.clip(np.asarray(y, float), 0.0, 1.0)
    g = np.repeat(y[..., None], 3, -1)
    if mode == 'exposure':
        out = g.copy()
        for lo, hi, c in FC_BANDS:
            m = (y >= lo) & (y < hi)
            out[m] = c
        return out
    if mode == 'spectrum':
        return hsv2rgb(0.66 * (1.0 - y)).reshape(y.shape + (3,))
    if mode == 'zones':
        z = np.floor(y * 10.0 + 0.5) / 10.0
        return np.repeat(z[..., None], 3, -1)
    out = g.copy()
    out[y >= 0.99] = (1.0, 0.0, 0.0)
    out[y <= 0.02] = (0.0, 0.2, 1.0)
    return out


def zebra_mask(y, lo, hi, width, angle_deg, shift=0.0):
    """Pixels the zebra paints: lo <= luma <= hi AND inside a stripe: fract((x cos a + y sin a + shift) / 2w) < 0.5
    (pixel centres, x right / y up px)."""
    H, W = y.shape
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    a = math.radians(angle_deg)
    d = (xx * math.cos(a) + yy * math.sin(a) + shift) / (2.0 * max(width, 1e-3))
    return (y >= lo) & (y <= hi) & ((d - np.floor(d)) < 0.5)


def sobel_mag(y):
    """|Sobel| / 4 of luma with edge clamp (a 0 -> 1 step reads 1.0), = the peaking measure."""
    p = np.pad(np.asarray(y, float), 1, mode='edge')
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.sqrt(gx * gx + gy * gy) / 4.0


GUIDES = ['none', '16:9', '2.39:1', '1.85:1', '4:3', '4:5', '1:1', '9:16']
GUIDE_ASPECT = [0.0, 16 / 9.0, 2.39, 1.85, 4 / 3.0, 0.8, 1.0, 9 / 16.0]


def guide_frame(W, H, aspect):
    """Centred frame of `aspect` (w/h) inside W x H: (x0, y0, w, h)."""
    if aspect <= 0:
        return 0.0, 0.0, float(W), float(H)
    if W / float(H) > aspect:
        w = H * aspect
        return (W - w) / 2.0, 0.0, w, float(H)
    h = W / aspect
    return 0.0, (H - h) / 2.0, float(W), h


def timecode(t, fps):
    t = max(float(t), 0.0)
    return int(t // 3600) % 24, int(t // 60) % 60, int(t) % 60, min(int((t % 1.0) * fps), max(int(fps) - 1, 0))


TC_EXPR = ("(lambda t, f: (int(t // 3600) % 24, int(t // 60) % 60, int(t) % 60, min(int((t % 1.0) * f), "
           "max(int(f) - 1, 0))))(max(0.0, (absTime.seconds - parent().par.Tcstart.eval() + parent().par.Tcoffset.eval()"
           ") if parent().par.Tcsource.menuIndex == 0 else (lambda lt, s: lt.tm_hour * 3600 + lt.tm_min * 60 + "
           "lt.tm_sec + s % 1.0)(__import__('time').localtime(), __import__('time').time())), "
           "parent().par.Tcfps.eval())")

# 8x8 ASCII 0x20-0x7E, 16 hex digits per glyph (row 0 top first, bit 0 = leftmost pixel). Public domain font8x8_basic
# (Daniel Hepper, github.com/dhepper/font8x8, from the IBM PC VGA font); own copy so FX_scope needs no other lane's file.
FONT_HEX = (
    '0000000000000000183C3C1818001800363600000000000036367F367F3636000C3E031E301F0C00006333180C6663001C361C6E3B336E00'
    '0606030000000000180C0606060C1800060C1818180C060000663CFF3C660000000C0C3F0C0C000000000000000C0C060000003F00000000'
    '00000000000C0C006030180C060301003E63737B6F673E000C0E0C0C0C0C3F001E33301C06333F001E33301C30331E00383C36337F307800'
    '3F031F3030331E001C06031F33331E003F3330180C0C0C001E33331E33331E001E33333E30180E00000C0C00000C0C00000C0C00000C0C06'
    '180C0603060C180000003F00003F0000060C1830180C06001E3330180C000C003E637B7B7B031E000C1E33333F3333003F66663E66663F00'
    '3C66030303663C001F36666666361F007F46161E16467F007F46161E16060F003C66030373667C003333333F333333001E0C0C0C0C0C1E00'
    '7830303033331E006766361E366667000F06060646667F0063777F7F6B63630063676F7B736363001C36636363361C003F66663E06060F00'
    '1E3333333B1E38003F66663E366667001E33070E38331E003F2D0C0C0C0C1E003333333333333F0033333333331E0C006363636B7F776300'
    '6363361C1C3663003333331E0C0C1E007F6331184C667F001E06060606061E0003060C18306040001E18181818181E00081C366300000000'
    '00000000000000FF0C0C18000000000000001E303E336E000706063E66663B0000001E3303331E003830303E33336E0000001E333F031E00'
    '1C36060F06060F0000006E33333E301F0706366E666667000C000E0C0C0C1E00300030303033331E070666361E3667000E0C0C0C0C0C1E00'
    '0000337F7F6B630000001F333333330000001E3333331E0000003B66663E060F00006E33333E307800003B6E66060F0000003E031E301F00'
    '080C3E0C0C2C18000000333333336E0000003333331E0C000000636B7F7F3600000063361C36630000003333333E301F00003F190C263F00'
    '380C0C070C0C38001818180018181800070C0C380C0C07006E3B000000000000')


def font_words():
    """FONT_HEX -> 190 uints: glyph c (code 32 + g) = words 2g (rows 0-3) and 2g+1 (rows 4-7), row r in bits 8(r%4)."""
    out = []
    for g in range(len(FONT_HEX) // 16):
        b = [int(FONT_HEX[16 * g + 2 * k:16 * g + 2 * k + 2], 16) for k in range(8)]
        out += [b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24, b[4] | b[5] << 8 | b[6] << 16 | b[7] << 24]
    return out


def glyph_bit(code, row, col):
    w = font_words()
    g = code - 32
    if g < 0 or g >= len(w) // 2:
        return 0
    return (w[2 * g + row // 4] >> (8 * (row % 4) + col)) & 1


LABEL_CHARS = 16


def label_expr(k):
    """Uniform component k (0..15) of the Label string as an ASCII code (space past the end, '?' outside ASCII)."""
    return ("(lambda s: (lambda c: c if 32 <= c < 127 else 63)(ord(s[%d])) if %d < len(s) else 32)"
            "(parent().par.Label.eval())" % (k, k))


# ------------------------------------------------------------------ live-check helpers (numpy readbacks)
def check_dir(d):
    """Compare a saved GPU readback with the reference. d holds meta.json {'kind': ...} + npy files.
    kind 'beam': gpu.npy (bh, bw, 4) state with Persist 0, points.npy (n, 4) path texels -> max abs / rel error.
    kind 'hist': gpu.npy bins (h, w, 4), src.npy input image -> exact count match ratio."""
    with open(os.path.join(d, 'meta.json')) as fh:
        meta = json.load(fh)
    gpu = np.load(os.path.join(d, 'gpu.npy')).astype(float)
    if meta['kind'] == 'beam':
        pts = np.load(os.path.join(d, 'points.npy')).astype(float)
        n = int(meta['np'])
        bh, bw = gpu.shape[:2]
        E = splat_ref(pts[:n, :2], pts[:n, 2], np.array([unpack_rgb(v) for v in pts[:n, 3]]), bw, bh,
                      meta['sigma'], meta['kn'], meta['dwell'], meta['lref'], meta['intensity'], bool(meta['mono']))
        ref = E @ np.asarray(LUMA709)
        err = np.abs(gpu[..., 3] - ref)
        return {'max': float(err.max()), 'rel': float(err.max() / max(ref.max(), 1e-9)), 'sum_gpu': float(gpu[..., 3].sum()),
                'sum_ref': float(ref.sum()), 'peak': float(ref.max())}
    if meta['kind'] == 'hist':
        src = np.load(os.path.join(d, 'src.npy')).astype(float)
        ref = hist_ref(src, meta['mode'], meta['step'], meta['lv'], meta['B'], meta['matrix'])
        got = np.rint(gpu[..., 0]).astype(int)
        return {'equal_bins': float((got == ref).mean()), 'total_gpu': int(got.sum()), 'total_ref': int(ref.sum()),
                'max_abs': int(np.abs(got - ref).max())}
    raise ValueError(meta['kind'])


BEAM_SNIPPET = """# allow-readback
import json, os
import numpy as np
m = op(%r)
d = %r
os.makedirs(d, exist_ok=True)
b, pth = m.op('beam'), m.op('path')
g = b.numpyArray(delayed=False)
pa = pth.numpyArray(delayed=False)
np.save(os.path.join(d, 'gpu.npy'), g)
np.save(os.path.join(d, 'points.npy'), pa[:16].reshape(-1, 4))
ev = lambda k, c: float(getattr(b.par, 'vec%%dvalue%%s' %% (k, c)).eval())
meta = {'kind': 'beam', 'np': int(round(float(pa[16, 1023, 0]))), 'sigma': ev(0, 'x'), 'kn': ev(0, 'y'),
        'dwell': ev(0, 'z'), 'lref': ev(0, 'w'), 'intensity': ev(1, 'x'), 'mono': ev(1, 'y'),
        'size': [int(g.shape[1]), int(g.shape[0])], 'alpha_sum': float(g[..., 3].sum()), 'alpha_max': float(g[..., 3].max())}
json.dump(meta, open(os.path.join(d, 'meta.json'), 'w'))
result = meta
"""

HIST_SNIPPET = """# allow-readback
import json, os
import numpy as np
m = op(%r)
d = %r
os.makedirs(d, exist_ok=True)
np.save(os.path.join(d, 'src.npy'), m.op('in1').numpyArray(delayed=False))
h = m.op('hist').numpyArray(delayed=False)
np.save(os.path.join(d, 'gpu.npy'), h)
p = m.par
meta = {'kind': 'hist', 'mode': p.Scope.eval(), 'step': int(p.Step.eval()), 'lv': int(p.Levels.eval()),
        'B': int(p.Bins.eval()), 'matrix': p.Matrix.menuIndex, 'total': float(h[..., 0].sum())}
json.dump(meta, open(os.path.join(d, 'meta.json'), 'w'))
result = meta
"""


def beam_snippet(module_path, out_dir):
    """td_exec code that saves a beam parity set (module with Persist 0): pass it as is (starts '# allow-readback'),
    in its own exec >= 2 frames after the last change (T-74); then `python3 -I builders/fx_scope_logic.py check d`."""
    return BEAM_SNIPPET % (module_path, out_dir)


def hist_snippet(module_path, out_dir):
    return HIST_SNIPPET % (module_path, out_dir)


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == 'check':
        print(check_dir(sys.argv[2]))
    else:
        print('usage: python3 -I builders/fx_scope_logic.py check <dir>')
