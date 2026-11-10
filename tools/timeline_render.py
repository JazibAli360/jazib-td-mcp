#!/usr/bin/env python3
"""TL_timeline phase 3, outside TD: offline audio mix + mux of a recorded take, and an A/V sync check.

  timeline_render.py mux <plan.json>          mix the take's audio (clips + master, ffmpeg) and mux it into the movie;
                                              writes <out>.report.json (ffprobe frames, audio samples, ok)
  timeline_render.py check <movie> [--fps N] [--in S] [--master-period 0.5 --master-phase 0.25]
                                              flash frames (video) vs click onsets (audio): offsets in seconds/frames

TD starts `mux` with Popen after the Movie File Out is finalised (never inside a cook). Pure logic:
builders/timeline_record_logic.py. Plan: docs/builds/timeline_phase3.md.
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import timeline_record_logic as RL  # noqa: E402


def tool(name):
    for p in (shutil.which(name), '/opt/homebrew/bin/' + name, '/usr/local/bin/' + name):
        if p and os.path.isfile(p):
            return p
    raise SystemExit('%s not found' % name)


def count_frames(path):
    out = subprocess.run([tool('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                          'stream=nb_read_frames,r_frame_rate,codec_name,pix_fmt,width,height', '-of', 'json', path],
                         capture_output=True, text=True).stdout
    st = (json.loads(out or '{}').get('streams') or [{}])[0]
    return st


def audio_info(path):
    out = subprocess.run([tool('ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                          'stream=codec_name,sample_rate,channels,duration_ts,duration', '-of', 'json', path],
                         capture_output=True, text=True).stdout
    return (json.loads(out or '{}').get('streams') or [{}])[0]


def has_audio(path):
    return bool(audio_info(path).get('codec_name'))


def mux(plan_path):
    plan = json.load(open(plan_path))
    video, out = plan['video'], plan['out']
    rep = {'plan': plan_path, 'video': video, 'out': out, 'frames_expected': plan['frames']}
    segs = [s for s in plan.get('segments', []) if os.path.isfile(s['src']) and has_audio(s['src'])]
    rep['segments'] = [{'id': s['id'], 'at': s['at'], 'dur': s['dur'], 'src_start': s['src_start']} for s in segs]
    total = plan['frames'] / float(plan['fps'])
    if segs:
        wav = out[:-4] + '_mix.wav'
        r = subprocess.run(RL.mix_cmd(segs, total, wav, tool('ffmpeg')), capture_output=True, text=True)
        if r.returncode:
            rep['error'] = 'mix: ' + r.stderr[-800:]
        else:
            r = subprocess.run(RL.mux_cmd(video, wav, out, tool('ffmpeg')), capture_output=True, text=True)
            if r.returncode:
                rep['error'] = 'mux: ' + r.stderr[-800:]
            else:
                os.remove(video)
                rep['audio'] = audio_info(out)
                rep['mix_wav'] = wav
    else:
        os.replace(video, out)
        rep['audio'] = None
    if 'error' not in rep:
        st = count_frames(out)
        rep['video_stream'] = st
        rep['frames_counted'] = int(st.get('nb_read_frames') or 0)
        rep['ok'] = rep['frames_counted'] == plan['frames']
    else:
        rep['ok'] = False
    with open(out + '.report.json', 'w') as f:
        json.dump(rep, f, indent=1)
    print(json.dumps(rep))
    return 0 if rep['ok'] else 1


def frame_means(path):
    raw = subprocess.run([tool('ffmpeg'), '-v', 'error', '-i', path, '-map', '0:v:0', '-vf', 'scale=16:16,format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    return [sum(raw[i:i + 256]) / (256 * 255.0) for i in range(0, len(raw) - 255, 256)]


def audio_samples(path, sr=48000):
    raw = subprocess.run([tool('ffmpeg'), '-v', 'error', '-i', path, '-map', '0:a:0', '-ac', '1', '-ar', str(sr),
                          '-f', 'f32le', '-'], capture_output=True).stdout
    return list(struct.unpack('<%df' % (len(raw) // 4), raw[:len(raw) // 4 * 4]))


def check(path, fps, t_in=0.0, period=0.5, phase=0.25):
    means = frame_means(path)
    fl = RL.flash_frames(means)
    sr = 48000
    on = RL.onsets(audio_samples(path, sr), sr, thresh=0.1)
    flash_t = [k / float(fps) for k in fl]
    clip_offs = RL.pair_offsets(flash_t, on, max_gap=0.12)
    # master clicks: expected at phase + period*j in timeline time -> output time = that - in
    dur = len(means) / float(fps)
    exp = []
    j = 0
    while True:
        t = phase + period * j - t_in
        j += 1
        if t >= dur:
            break
        if t >= 0:
            exp.append(t)
    master_offs = RL.pair_offsets(exp, on, max_gap=0.12)
    fr = 1.0 / fps
    rep = {'movie': path, 'fps': fps, 'frames': len(means), 'flash_frames': fl, 'onsets': [round(x, 5) for x in on],
           'clip_offsets_s': [round(x, 6) for x in clip_offs],
           'clip_offset_max_frames': round(max([abs(x) for x in clip_offs] or [0]) / fr, 4),
           'master_offsets_s': [round(x, 6) for x in master_offs],
           'master_offset_max_frames': round(max([abs(x) for x in master_offs] or [0]) / fr, 4)}
    rep['ok'] = bool(clip_offs) and rep['clip_offset_max_frames'] < 1 and rep['master_offset_max_frames'] < 1
    print(json.dumps(rep))
    return 0 if rep['ok'] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('mux')
    m.add_argument('plan')
    c = sub.add_parser('check')
    c.add_argument('movie')
    c.add_argument('--fps', type=float, default=60.0)
    c.add_argument('--in', dest='t_in', type=float, default=0.0)
    c.add_argument('--master-period', type=float, default=0.5)
    c.add_argument('--master-phase', type=float, default=0.25)
    a = ap.parse_args(argv)
    if a.cmd == 'mux':
        return mux(a.plan)
    return check(a.movie, a.fps, a.t_in, a.master_period, a.master_phase)


if __name__ == '__main__':
    sys.exit(main())
