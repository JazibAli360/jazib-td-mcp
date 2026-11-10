"""Standalone check of kind 1 (Core ML depth, Depth Anything V2 Small) through the socket. Stdlib + optional numpy
(runs on native python3 and on TD 2's own x86_64 Python 3.11 under Rosetta, outside TD). Frames: a raw BGRA dump at
the model size, rows bottom-up (as TD numpyArray()):
    ffmpeg -i media/webcam/webcam_ref_5s.mp4 -vf scale=518:392,vflip -pix_fmt bgra -f rawvideo frames.bgra
    python3 -I helpers/vision_bridge/depth_socket_test.py frames.bgra 518 392 out_dir [paced]
`paced`: poll once per 16.7 ms like a 60 fps TD frame loop (round trips quantised to frames); default: as fast as
one-in-flight allows. Writes out_dir/depth_<mode>.json (per answer: rtt, compute, wait, percentiles, field stats)
and out_dir/depth_<frame>.pgm for frames 0, 75, 140 (normalized field, 255 = near, top row first).
"""
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'builders'))
import camera_bridge as cb  # noqa: E402
import depth_cam_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:  # stats need numpy; latency still measured
    np = None

raw, w, h, outdir = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
paced = len(sys.argv) > 5 and sys.argv[5] == 'paced'
os.makedirs(outdir, exist_ok=True)
fsz = w * h * 4
with open(raw, 'rb') as f:
    blob = f.read()
nframes = len(blob) // fsz
model = os.path.join(HERE, 'assets', L.MODEL_NAME)
sock = cb.default_socket_path('dcst_{}'.format(os.getpid()))
c = cb.BridgeClient(sock, helper=os.path.join(HERE, 'build', 'jzb_vision_bridge'), args=L.helper_args(model),
                    timeout_s=10.0)
ctl = L.Controller()
res = {'python': sys.version.split()[0], 'machine': platform.machine(), 'numpy': np.__version__ if np else None,
       'w': w, 'h': h, 'paced': paced, 'model_problem': L.model_problem(model), 'answers': []}
t0 = time.monotonic()
field = None
idx = 0
first_ok = None
not_ready = 0
errors = []
step_ms = []
SAVE = (0, 75, 140)
while idx < nframes and time.monotonic() - t0 < 120:
    now = time.monotonic()
    for r in c.pump(now):
        if r.status == cb.ST_NOT_READY:
            not_ready += 1
            ctl.not_ready(now, r.frame_id)
            continue
        if r.status != cb.ST_OK:
            errors.append([r.frame_id, r.status_name(), r.text])
            ctl.error(now, r.frame_id, r.text)
            if len(errors) > 5:
                idx = nframes
            continue
        L.check_answer(r.data, r.width, r.height)
        e = ctl.result(now, r.frame_id, r.p_lo, r.p_hi, r.width, r.height, 0.5)
        if e is None:
            continue
        if first_ok is None:
            first_ok = now - t0
        a = {'frame': r.frame_id, 'rtt_ms': round((now - e['sent_t']) * 1000, 1), 'compute_ms': round(r.compute_ms, 1),
             'wait_ms': round(r.wait_ms, 2), 'size': [r.width, r.height], 'p_lo': round(r.p_lo, 4),
             'p_hi': round(r.p_hi, 4), 'range_lo': round(e['lo'], 4), 'span': round(e['span'], 4)}
        if np is not None:
            d = np.frombuffer(r.data, dtype=np.float32).reshape(r.height, r.width)
            ts = time.perf_counter()
            field = L.field_step_np(np, field, d, e['lo'], e['span'], e['k'])
            step_ms.append((time.perf_counter() - ts) * 1000.0)
            q = np.percentile(d, [0, 2, 50, 98, 100])
            fifth = r.height // 5
            a.update({'raw_pct_0_2_50_98_100': [round(float(x), 4) for x in q],
                      'field_mean': round(float(field.mean()), 4),
                      # rows bottom-up: [:fifth] = bottom of the picture
                      'bottom_fifth': round(float(field[:fifth].mean()), 4),
                      'top_fifth': round(float(field[-fifth:].mean()), 4),
                      'centre': round(float(field[r.height // 3:2 * r.height // 3, r.width // 3:2 * r.width // 3].mean()), 4)})
            if r.frame_id in SAVE:
                img = (np.flipud(field) * 255.0 + 0.5).clip(0, 255).astype(np.uint8)
                with open(os.path.join(outdir, 'depth_{}.pgm'.format(r.frame_id)), 'wb') as g:
                    g.write('P5 {} {} 255\n'.format(r.width, r.height).encode() + img.tobytes())
        res['answers'].append(a)
        idx += 1
    now = time.monotonic()
    if idx < nframes and ctl.want_request(now, c.can_submit()):
        # paced: send the frame the "TD clock" is on (newest wins); fast: every frame in order
        fid = min(nframes - 1, int((now - t0) * 30)) if paced and first_ok is not None else idx
        if paced and first_ok is not None:
            idx = max(idx, fid)
        if c.submit(cb.KIND_DEPTH, fid, now, w, h, blob[fid * fsz:(fid + 1) * fsz], cb.FL_BOTTOM_UP, now=now):
            ctl.sent_frame(now, fid)
    time.sleep(1.0 / 60.0 if paced else 0.001)
res.update({'not_ready': not_ready, 'first_ok_s': first_ok, 'errors': errors, 'stats': c.stats(),
            'wall_s': round(time.monotonic() - t0, 2)})
info = None
try:  # the helper's own info (model load time) over a fresh connection, before closing
    c2 = cb.BridgeClient(sock)
    c2.ensure(time.monotonic())
    c2.submit(cb.KIND_INFO, 1, 0.0)
    t1 = time.monotonic()
    while info is None and time.monotonic() - t1 < 2:
        for r in c2.pump():
            info = json.loads(r.text)
        time.sleep(0.005)
    c2.close(stop_helper=False)
except Exception as ex:  # noqa: BLE001 - diagnostics only
    info = {'error': str(ex)}
c.close()
A = res['answers']
rt = [x['rtt_ms'] for x in A]
cm = [x['compute_ms'] for x in A]
span_s = (A[-1]['frame'] - A[0]['frame']) / 30.0 if len(A) > 1 else 0
res['summary'] = {
    'answers': len(A), 'rtt_median': L.median(rt), 'rtt_p95': L.pct(rt, 0.95), 'compute_median': L.median(cm),
    'compute_p95': L.pct(cm, 0.95), 'answers_per_s': round(len(A) / max(res['wall_s'] - (first_ok or 0), 1e-3), 1),
    'clip_seconds_covered': round(span_s, 2), 'field_step_ms_median': L.median(step_ms),
    'field_step_ms_p95': L.pct(step_ms, 0.95), 'helper_info': info}
if A and 'bottom_fifth' in A[0]:
    for k in ('p_lo', 'p_hi', 'bottom_fifth', 'top_fifth', 'centre', 'field_mean'):
        v = [x[k] for x in A]
        res['summary'][k + '_min_med_max'] = [min(v), L.median(v), max(v)]
with open(os.path.join(outdir, 'depth_{}.json'.format('paced' if paced else 'fast')), 'w') as f:
    json.dump(res, f, indent=1)
print(json.dumps({'python': res['python'], 'machine': res['machine'], 'not_ready': not_ready, 'first_ok_s': first_ok,
                  'errors': errors[:3], 'summary': res['summary']}, indent=1))
