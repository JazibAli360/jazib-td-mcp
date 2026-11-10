"""Standalone check of kind 5 (face landmarks) through the socket, stdlib only (runs on native python3 and on TD 2's
own x86_64 Python). Frames: a raw BGRA dump made with ffmpeg, rows bottom-up (as TD numpyArray()):
    ffmpeg -i clip.mp4 -vf scale=640:-2,vflip -pix_fmt bgra -f rawvideo frames.bgra
    python3 -I helpers/vision_bridge/landmarks_socket_test.py frames.bgra 640 360 out.json
Prints a summary; writes per-frame results (faces, rtt, compute ms, measures) to out.json.
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
import face_track_logic as ftl  # noqa: E402

raw, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
fsz = w * h * 4
with open(raw, 'rb') as f:
    blob = f.read()
nframes = len(blob) // fsz
sock = cb.default_socket_path('ftlm_{}'.format(os.getpid()))
c = cb.BridgeClient(sock, helper=os.path.join(HERE, 'build', 'jzb_vision_bridge'),
                    args=['--no-depth', '--no-seg', '--no-faces'])
res = {'python': sys.version.split()[0], 'machine': platform.machine(), 'w': w, 'h': h, 'frames': [], 'layout': None}
t0 = time.monotonic()
not_ready = 0
idx = 0
sent_at = {}
first_ok = None
while idx < nframes and time.monotonic() - t0 < 60:
    if c.can_submit():
        c.submit(cb.KIND_LANDMARKS, idx, time.monotonic(), w, h, blob[idx * fsz:(idx + 1) * fsz], cb.FL_BOTTOM_UP)
        sent_at[idx] = time.monotonic()
    for r in c.pump():
        if r.status == cb.ST_NOT_READY:
            not_ready += 1
            continue
        if r.status != cb.ST_OK:
            res['frames'].append({'frame': r.frame_id, 'status': r.status_name(), 'text': r.text})
            idx += 1
            continue
        if first_ok is None:
            first_ok = time.monotonic() - t0
        faces = ftl.parse_landmarks(r.data, r.width, r.height, r.text)
        if faces:
            res['layout'] = ftl.parse_layout(r.text)
        fr = {'frame': r.frame_id, 'rtt_ms': round((time.monotonic() - sent_at[r.frame_id]) * 1000, 1),
              'compute_ms': round(r.compute_ms, 1), 'faces': len(faces)}
        if faces:
            f = faces[0]
            m = ftl.measures(f, w / float(h))
            rg = f['regions']
            fr.update({'rect': [round(v, 4) for v in f['rect']], 'conf': round(f['conf'], 3),
                       'roll_deg': None if f['roll'] is None else round(f['roll'] * 57.2958, 1),
                       'yaw_deg': None if f['yaw'] is None else round(f['yaw'] * 57.2958, 1),
                       'pitch_deg': None if f['pitch'] is None else round(f['pitch'] * 57.2958, 1),
                       'eye_l_raw': round(m['eye_l_raw'], 3), 'eye_r_raw': round(m['eye_r_raw'], 3),
                       'mouth_raw': round(m['mouth_raw'], 3), 'eyeroll_deg': round(m['roll'] * 57.2958, 1),
                       'eye_l_cx': round(ftl.centroid(rg['eye_l'])[0], 4) if rg['eye_l'] else None,
                       'eye_r_cx': round(ftl.centroid(rg['eye_r'])[0], 4) if rg['eye_r'] else None,
                       'order_ok': bool(rg['eye_l'] and rg['nose'] and rg['lips_outer'] and rg['jaw'] and
                                        ftl.centroid(rg['eye_l'])[1] < ftl.centroid(rg['nose'])[1] <
                                        ftl.centroid(rg['lips_outer'])[1] < max(p[1] for p in rg['jaw']))})
            if 'first_face' not in res:
                res['first_face'] = f
        res['frames'].append(fr)
        idx += 1
    time.sleep(0.002)
res['not_ready'] = not_ready
res['first_ok_s'] = first_ok
res['stats'] = c.stats()
c.close()
oks = [f for f in res['frames'] if 'faces' in f]
withf = [f for f in oks if f['faces'] > 0]
rt = sorted(f['rtt_ms'] for f in oks)
cm = sorted(f['compute_ms'] for f in oks)
res['summary'] = {'frames': len(oks), 'with_face': len(withf), 'order_ok': sum(1 for f in withf if f['order_ok']),
                  'rtt_median': rt[len(rt) // 2] if rt else None, 'rtt_p95': rt[int(len(rt) * 0.95)] if rt else None,
                  'compute_median': cm[len(cm) // 2] if cm else None, 'layout': res['layout']}
with open(out, 'w') as f:
    json.dump(res, f, indent=1)
print(json.dumps({'python': res['python'], 'machine': res['machine'], 'not_ready': not_ready,
                  'first_ok_s': first_ok, 'summary': res['summary']}))
