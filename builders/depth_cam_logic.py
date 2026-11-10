"""depth_cam pure logic (no TD, stdlib only; numpy only where a caller passes the module in).

Depth from the camera through helpers/vision_bridge (kind 1 = Core ML Depth Anything V2 Small, 518x392 float32,
larger = nearer, rows bottom-up). Copied verbatim into the COMP's `depth_cam_logic` Text DAT by builders/depth_cam.py,
so the COMP stands alone. Tests: test/test_depth_cam.py.

Ported (copied, then cut down) from td-port/lib/depth_fx.py (read only, 26 Oct 2026), which ports stagelab
ffgl/common/DepthLogic.h (sha1 c80fc2eef352): the 2 % / 98 % percentiles (the helper sends them with every map), the
range eased over time (at least 0.25 s) and the per-pixel ease toward each new result (DepthField.Add). Float32
rounding is emulated (f32) as in td-port, so the numbers match the C++.

Depth values here: `field` = 0 (far) .. 1 (near), rows bottom-up (GL / TD numpy order), the model's own size.
"""
import math
import os
import struct

KIND_DEPTH = 1
MODEL_IN = (518, 392)          # Depth Anything V2 Small input (DepthFX MODEL_W/H); the helper ScaleFills to it
MODEL_NAME = 'DepthAnythingV2SmallF16.mlmodelc'
MODES = ('depth', 'fog', 'slice', 'outline')
MODE_LABELS = ('Depth view', 'Fog', 'Slice', 'Outline')
MIN_INTERVAL = 0.05            # at most 20 requests per second (DepthFX.cpp Read())
NOT_READY_RETRY = 0.5          # model loading: ask again after 0.5 s
ERROR_RETRY = 1.0              # helper error (e.g. model load failed): ask once a second
FAKE_SIZE = (130, 98)          # Fakedepth: a quarter of the model size, cheap on TD's Rosetta numpy


def f32(x):
    """Round to IEEE float32, as the C++ stores it."""
    return struct.unpack('<f', struct.pack('<f', x))[0]


def ease_step(dt, tau):
    """DepthLogic EaseStep: share of the way to go this step (exponential, time constant tau seconds)."""
    dt, tau = f32(dt), f32(tau)
    if tau <= f32(1e-4):
        return 1.0
    return f32(1.0 - f32(math.exp(f32(-f32(max(dt, 0.0)) / tau))))


def depth_tau(smoothing):
    """Smoothing 0..1 -> time constant 0..0.6 s."""
    return f32(f32(0.6) * min(max(f32(smoothing), 0.0), 1.0))


def percentiles(values, low_share=0.02, high_share=0.98):
    """DepthLogic Percentiles: (lo, hi) of the low/high percentile via a 1024-bin histogram over min..max.
    Reference port (the helper computes the same in C++ and sends it in the answer header)."""
    n = len(values)
    if n == 0:
        return 0.0, 1.0
    v = [f32(x) for x in values]
    mn, mx = min(v), max(v)
    if not mx > mn:
        return mn, f32(mn + f32(1e-3))
    bins = 1024
    k = f32((bins - 1) / f32(mx - mn))
    h = [0] * bins
    for x in v:
        h[min(max(int(f32(f32(x - mn) * k)), 0), bins - 1)] += 1
    low_n, high_n = int(f32(f32(low_share) * n)), int(f32(f32(high_share) * n))
    acc, lo, hi, have_lo = 0, 0, bins - 1, False
    for b in range(bins):
        acc += h[b]
        if not have_lo and acc > low_n:
            lo, have_lo = b, True
        if acc >= high_n:
            hi = b
            break
    rlo = f32(mn + f32(lo / k))
    rhi = max(f32(mn + f32((hi + 1) / k)), f32(rlo + f32(1e-3)))
    return rlo, rhi


class RangeEaser(object):
    """The scalar half of DepthField.Add: the range eases toward each result's percentiles (at least 0.25 s); the
    first result (or the first after a reset / size change) is taken as is. Returns what the field step needs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.lo, self.hi = 0.0, 1.0
        self.size = None
        self.results = 0

    def add(self, p_lo, p_hi, w, h, dt, smoothing):
        first = self.size != (w, h)
        k_range = 1.0 if first else ease_step(dt, max(depth_tau(smoothing), f32(0.25)))
        self.lo = f32(self.lo + f32(f32(f32(p_lo) - self.lo) * k_range))
        self.hi = f32(self.hi + f32(f32(f32(p_hi) - self.hi) * k_range))
        span = max(f32(self.hi - self.lo), f32(1e-4))
        k = 1.0 if first else ease_step(dt, depth_tau(smoothing))
        self.size = (w, h)
        self.results += 1
        return {'lo': self.lo, 'span': span, 'k': k, 'first': first}


def field_step(field, raw, lo, span, k):
    """Per-pixel half, pure Python reference: field += (clamp((raw - lo) / span, 0, 1) - field) * k."""
    out = []
    for f, r in zip(field, raw):
        d = min(max(f32(f32(f32(r) - lo) / span), 0.0), 1.0)
        out.append(f32(f + f32(f32(d - f) * k)))
    return out


def field_step_np(np, field, raw, lo, span, k):
    """The same with numpy (TD runtime). field None (first result) -> the normalized map itself. float32 out."""
    d = np.clip((raw.astype(np.float32) - np.float32(lo)) / np.float32(span), 0.0, 1.0).astype(np.float32)
    if field is None or field.shape != d.shape or k >= 1.0:
        return d
    field += (d - field) * np.float32(k)
    return field


def bytes_from_bgra_float(np, a):
    """TD numpyArray() of the `detect_bgra` TOP (float32 h x w x 4, 0..1, channels ALREADY swapped to B G R A on
    the GPU by a Reorder TOP, from an 8-bit fixed TOP so values stay in 0..1) -> BGRA8 bytes, rows as given.
    0.47 ms at 518x392 on TD's x86_64 numpy under Rosetta vs 2.5 ms for camera_bridge.bgra_bytes (fancy index +
    clip), measured 26 Oct outside TD."""
    return (a * np.float32(255.0) + np.float32(0.5)).astype(np.uint8).tobytes()


def check_answer(data, w, h):
    """A kind-1 answer's payload must be w*h float32. Returns the sample count; ValueError otherwise."""
    if w <= 0 or h <= 0:
        raise ValueError('empty depth map {}x{}'.format(w, h))
    if len(data) != 4 * w * h:
        raise ValueError('depth payload {} bytes, expected {}'.format(len(data), 4 * w * h))
    return w * h


def model_problem(path):
    """'' when `path` looks like a compiled Core ML model folder, else why not (shown as the COMP status)."""
    if not path:
        return 'model path empty'
    if not os.path.isdir(path):
        return 'model missing: {}'.format(path)
    if not any(os.path.exists(os.path.join(path, n)) for n in ('coremldata.bin', 'model.mil')):
        return 'not a compiled Core ML model: {}'.format(path)
    return ''


def helper_args(model_path):
    """serve flags: depth only (no segmentation / faces / landmarks warm-ups), explicit model path."""
    return ['--no-seg', '--no-faces', '--no-landmarks', '--model', model_path]


def tri(x):
    """Triangle wave 0 -> 1 -> 0 over one unit of x."""
    x = x - math.floor(x)
    return 2.0 * x if x < 0.5 else 2.0 * (1.0 - x)


def slice_center(t, center, speed):
    """Slice centre: `center` when speed is 0, else a sweep far <-> near at `speed` cycles per second that passes
    through `center` at t = 0 (going nearer)."""
    c = min(max(float(center), 0.0), 1.0)
    if not speed:
        return c
    return tri(float(t) * float(speed) + c * 0.5)


def mode_index(mode):
    return MODES.index(mode) if mode in MODES else 0


def fake_depth(x, y, t, exp=math.exp, cos=math.cos, sin=math.sin):
    """Synthetic nearness for Fakedepth (test without the helper). x, y = uv 0..1 (y up), scalars or numpy arrays
    (pass np.exp / np.cos / np.sin). Floor near at the bottom, far at the top + a near blob circling the centre."""
    bx = 0.5 + 0.25 * cos(t * 0.8)
    by = 0.45 + 0.15 * sin(t * 0.8)
    blob = exp(-(((x - bx) * 3.2) ** 2 + ((y - by) * 2.4) ** 2))
    ground = 0.55 * (1.0 - y)
    return ground + (1.0 - ground) * 0.85 * blob


class Controller(object):
    """Per-frame decisions for the TD runtime (no TD calls): when to read back + send, what an answer means, whether
    there is depth to show. A reset (Active off, source size change, reconnect) drops the field: answers for frames
    sent before it are ignored (`epoch`), so a stale map is never shown. After `hold` seconds without a good answer
    the depth is dropped too, so the effects pass the video through (helper dead / stalled)."""

    def __init__(self):
        self.easer = RangeEaser()
        self.epoch = 0
        self.sent = {}            # frame id -> (epoch, time sent)
        self.has_depth = False
        self.last_read = -1e9
        self.last_result_t = -1.0
        self.status = 'off'
        self.ignored = 0

    def reset(self, why):
        self.epoch += 1
        self.sent.clear()
        self.easer.reset()
        self.has_depth = False
        self.last_result_t = -1.0
        self.status = why

    def want_request(self, now, can_submit):
        """True when a frame should be read back and sent now (one in flight is the client's job)."""
        return bool(can_submit) and now - self.last_read >= MIN_INTERVAL

    def sent_frame(self, now, frame_id):
        self.sent[frame_id] = (self.epoch, now)
        self.last_read = now
        if len(self.sent) > 8:  # bounded bookkeeping (one in flight; a few kept for late answers)
            for k in sorted(self.sent)[:-8]:
                del self.sent[k]

    def not_ready(self, now, frame_id):
        """The helper is still loading the model: forget that request, ask again in NOT_READY_RETRY s."""
        self.sent.pop(frame_id, None)
        self.status = 'loading model'
        self.last_read = now + NOT_READY_RETRY - MIN_INTERVAL

    def error(self, now, frame_id, text):
        self.sent.pop(frame_id, None)
        self.status = 'error: ' + (text or 'unknown')
        self.last_read = now + ERROR_RETRY - MIN_INTERVAL

    def result(self, now, frame_id, p_lo, p_hi, w, h, smoothing):
        """A good answer: the field-step numbers (dict lo span k first, plus 'sent_t'), or None when it is stale."""
        sent = self.sent.pop(frame_id, None)
        if sent is None or sent[0] != self.epoch:
            self.ignored += 1
            return None
        dt = 0.0 if self.last_result_t < 0 else min(max(now - self.last_result_t, 0.0), 1.0)
        self.last_result_t = now
        e = self.easer.add(p_lo, p_hi, w, h, dt, smoothing)
        e['sent_t'] = sent[1]
        self.has_depth = True
        self.status = 'ok'
        return e

    def showing(self, now, hold):
        """Is there depth to show? Drops it (reset) after `hold` s without a good answer."""
        if self.has_depth and self.last_result_t >= 0 and now - self.last_result_t > max(float(hold), 0.05):
            self.reset('no answer for {:.1f} s: pass-through'.format(float(hold)))
        return self.has_depth


def median(v):
    s = sorted(v)
    return s[len(s) // 2] if s else None


def pct(v, q):
    s = sorted(v)
    return s[min(len(s) - 1, int(len(s) * q))] if s else None


def info_rows(d):
    """Key/value rows for the COMP's `info` table from a plain stats dict (missing keys -> '')."""
    keys = ('status', 'backend', 'helper_pid', 'have_depth', 'map_size', 'range_lo', 'range_hi', 'latency_ms_median',
            'latency_ms_p95', 'compute_ms_median', 'answers_per_s', 'answers', 'ignored', 'restarts',
            'python_ms_per_frame_median', 'python_ms_answer_frame_median', 'last_error')
    rows = [('key', 'value')]
    for k in keys:
        v = d.get(k, '')
        if isinstance(v, float):
            v = round(v, 3)
        rows.append((k, '' if v is None else str(v)))
    return rows
