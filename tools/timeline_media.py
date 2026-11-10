#!/usr/bin/env python3
"""TL_timeline phase 2: media info + proxies for clip sources, OUTSIDE TouchDesigner (never in TD's cook).

For each source: ffprobe -> output/timeline/media/<key>.json ({src, fps, frames, w, h, dur, proxy, audio}); with --proxies
also an All-Intra H.264 proxy (half size, same fps + frame count) at output/timeline/proxies/<key>/<name>_proxy.mp4,
checked with ffprobe (frame count must match). TL_timeline reads the json files (Refreshmedia pulse / clips change).

    python3 -I tools/timeline_media.py media/demo/clips/*.mp4                # probe only
    python3 -I tools/timeline_media.py --proxies --jobs 3 media/demo/clips/*.mp4
    python3 -I tools/timeline_media.py --proxies --table clips.tsv          # sources from a clips table (src column)
    python3 -I tools/timeline_media.py ... --background                     # detach, log to output/timeline/media.log

Paths relative to the repo root are fine. Existing proxies are kept unless --force. Exit code 1 if any source failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'builders'))
import timeline_clips_logic as L  # noqa: E402

CACHE = os.path.join(REPO, 'output', 'timeline', 'media')
PROXIES = os.path.join(REPO, 'output', 'timeline', 'proxies')


def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    for d in ('/opt/homebrew/bin', '/usr/local/bin', '/usr/bin'):
        if os.path.exists(os.path.join(d, name)):
            return os.path.join(d, name)
    raise SystemExit('%s not found' % name)


def probe(path, ffprobe):
    r = subprocess.run(L.probe_cmd(path, ffprobe), capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError('ffprobe failed: %s' % r.stderr.strip()[:300])
    info = L.parse_probe(r.stdout)
    if not info.get('fps'):
        raise RuntimeError('no video stream / frame rate')
    return info


def has_audio(path, ffprobe):
    r = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=codec_name',
                        '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and bool(r.stdout.strip())


def one(src, args, ffmpeg, ffprobe):
    src = L.resolve_path(src, REPO)
    if not os.path.isfile(src):
        return src, False, 'missing file'
    try:
        info = probe(src, ffprobe)
        info['src'] = src
        info['audio'] = has_audio(src, ffprobe)   # phase 3: clip audio (live Audio File In + offline mix)
        info['proxy'] = ''
        px = L.proxy_path(src, PROXIES)
        if args.proxies:
            if args.force or not os.path.isfile(px):
                os.makedirs(os.path.dirname(px), exist_ok=True)
                tmp = px[:-4] + '.part.mp4'
                r = subprocess.run(L.proxy_cmd(src, tmp, ffmpeg, args.scale, args.crf), capture_output=True,
                                   text=True, timeout=3600)
                if r.returncode != 0:
                    raise RuntimeError('ffmpeg failed: %s' % r.stderr.strip()[:300])
                os.replace(tmp, px)
            pi = probe(px, ffprobe)
            if pi['frames'] != info['frames'] or abs(pi['fps'] - info['fps']) > 1e-3:
                raise RuntimeError('proxy mismatch: %s frames @ %.3f vs source %s @ %.3f'
                                   % (pi['frames'], pi['fps'], info['frames'], info['fps']))
            info['proxy'] = px
            info['proxy_w'], info['proxy_h'] = pi['w'], pi['h']
        elif os.path.isfile(px):
            info['proxy'] = px
        os.makedirs(CACHE, exist_ok=True)
        with open(L.media_info_path(src, CACHE), 'w') as f:
            json.dump(info, f, indent=1, sort_keys=True)
        return src, True, '%d frames @ %.3f fps %dx%d%s' % (info['frames'], info['fps'], info['w'], info['h'],
                                                             (' proxy ' + px) if info['proxy'] else '')
    except Exception as e:  # noqa: BLE001
        return src, False, str(e)


def sources_from_table(path):
    with open(path) as f:
        rows = [line.rstrip('\n').split('\t') for line in f if line.strip()]
    return sorted(set(c['src'] for c in L.parse_clips(rows)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('sources', nargs='*')
    ap.add_argument('--table', help='clips table as TSV (header with a src column)')
    ap.add_argument('--proxies', action='store_true', help='also make All-Intra H.264 proxies')
    ap.add_argument('--force', action='store_true', help='remake existing proxies')
    ap.add_argument('--scale', type=float, default=0.5)
    ap.add_argument('--crf', type=int, default=20)
    ap.add_argument('--jobs', type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    ap.add_argument('--background', action='store_true', help='detach and log to output/timeline/media.log')
    a = ap.parse_args(argv)
    srcs = list(a.sources) + (sources_from_table(a.table) if a.table else [])
    if not srcs:
        ap.error('no sources')
    if a.background:
        log = os.path.join(REPO, 'output', 'timeline', 'media.log')
        os.makedirs(os.path.dirname(log), exist_ok=True)
        rest = [x for x in (argv if argv is not None else sys.argv[1:]) if x != '--background']
        with open(log, 'a') as lf:
            p = subprocess.Popen([sys.executable, '-I', os.path.abspath(__file__)] + rest, stdout=lf, stderr=lf,
                                 stdin=subprocess.DEVNULL, start_new_session=True, cwd=REPO)
        print('background pid %d, log %s' % (p.pid, log))
        return 0
    ffmpeg, ffprobe = find_tool('ffmpeg'), find_tool('ffprobe')
    bad = 0
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for src, ok, msg in ex.map(lambda s: one(s, a, ffmpeg, ffprobe), srcs):
            print('%s %s: %s' % ('ok  ' if ok else 'FAIL', src, msg), flush=True)
            bad += 0 if ok else 1
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
