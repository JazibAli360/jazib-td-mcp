#!/usr/bin/env python3
"""Offline datamosh / codec-corruption media prep (DG-03). ffmpeg + Python 3 stdlib only; no TouchDesigner.

  python3 tools/mosh.py ifdrop   IN OUT [--cuts 2,4] [--gop 300] [--size 480] [--fps 30] [--codec prores|hap|h264]
  python3 tools/mosh.py bloom    IN OUT --at 1.0 --repeat 40 [...]   duplicate one P-frame N times (P-frame bloom)
  python3 tools/mosh.py noise    IN OUT [--amount 20000] [--seed 1]  random byte flips in the bitstream
  python3 tools/mosh.py transition A B OUT [--dur 2]                 A's I-frame + B's P-frames (two-clip mosh)
  python3 tools/mosh.py preset   NAME IN OUT [--b B]                 glitch presets (list: presets)
  python3 tools/mosh.py info     FILE                                frame counts per picture type

Method (FX1 3.3): the source is encoded to MPEG-4 Part 2 elementary stream (-bf 0, big GOP) which is robust to
cut-and-paste of frames; the stream is edited at VOP level (start code 00 00 01 B6, coding type in the top 2 bits of
the next byte: 0 = I, 1 = P); I-drop can also be done by ffmpeg's `-bsf:v noise=drop=...`. The edited stream is decoded
and re-encoded to a safe delivery codec (ProRes 422 default; HAP via ffmpeg `hap` when the build has it; H.264 fallback).
Nothing is overwritten: OUT must not exist unless --force. No safety limiter here (user rule); flashing is the user's call.
"""
import argparse
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

FFMPEG = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
FFPROBE = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
VOP = b'\x00\x00\x01\xb6'

PRESETS = {
    # name: (description, mode, kwargs)
    'drop_hold': ('first I-frame only, long GOP: motion drags the opening frame', 'ifdrop', {}),
    'drop_cuts': ('keyframes forced at 1/3 and 2/3 then dropped: scene motion smears across cuts', 'ifdrop', {'cuts_frac': (1 / 3, 2 / 3)}),
    'bloom_mid': ('one mid-clip P-frame repeated 45x: motion vectors keep pushing the picture', 'bloom', {'at_frac': 0.5, 'repeat': 45}),
    'bloom_burst': ('short P-frame repeat 12x at 1/4', 'bloom', {'at_frac': 0.25, 'repeat': 12}),
    'noise_light': ('light bitstream flips', 'noise', {'amount': 60000}),
    'noise_heavy': ('heavy bitstream flips', 'noise', {'amount': 8000}),
    'mosh_cut': ('two-clip mosh: A then B drags from A (needs --b)', 'transition', {}),
}


class MoshError(RuntimeError):
    pass


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise MoshError('%s failed: %s' % (os.path.basename(cmd[0]), p.stderr.strip()[-600:]))
    return p


# ---------- probing ----------
def probe(path):
    """{'frames': int, 'fps': float, 'w': int, 'h': int, 'dur': float, 'types': {'I':n,'P':n,'B':n}}"""
    p = run([FFPROBE, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pict_type',
             '-of', 'csv=p=0', path])
    types = {}
    for ln in p.stdout.split():
        t = ln.strip(',')[:1]
        if t:
            types[t] = types.get(t, 0) + 1
    s = run([FFPROBE, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
             'stream=width,height,r_frame_rate,duration', '-of', 'default=nw=1', path]).stdout
    kv = dict(l.split('=', 1) for l in s.split() if '=' in l)
    num, _, den = kv.get('r_frame_rate', '30/1').partition('/')
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    n = sum(types.values())
    try:
        dur = float(kv.get('duration', ''))
    except ValueError:
        dur = n / fps
    return {'frames': n, 'fps': fps, 'w': int(kv['width']), 'h': int(kv['height']), 'dur': dur, 'types': types}


# ---------- encode / decode ----------
def encode_m4v(src, dst, size=480, fps=30, gop=100000, q=3, cuts=(), start=None, dur=None):
    """Source -> MPEG-4 Part 2 elementary stream, no B-frames, huge GOP (keyframes only at 0 and the cuts)."""
    cmd = [FFMPEG, '-v', 'error', '-y']
    if start:
        cmd += ['-ss', str(start)]
    if dur:
        cmd += ['-t', str(dur)]
    cmd += ['-i', src, '-an', '-vf', 'scale=%d:-2:flags=bicubic,fps=%s,format=yuv420p' % (size, fps),
            '-c:v', 'mpeg4', '-q:v', str(q), '-g', str(gop), '-bf', '0', '-sc_threshold', '0']
    if cuts:
        cmd += ['-force_key_frames', ','.join('%.3f' % c for c in cuts)]
    cmd += ['-f', 'm4v', dst]
    run(cmd)


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def split_vops(data):
    """(header_bytes, [vop_bytes...]) for an MPEG-4 Part 2 elementary stream."""
    idx = [m.start() for m in re.finditer(re.escape(VOP), data)]
    if not idx:
        raise MoshError('no VOPs found in stream')
    return data[:idx[0]], [data[a:b] for a, b in zip(idx, idx[1:] + [len(data)])]


def vop_type(v):
    return 'IPBS'[v[4] >> 6]


def write_stream(path, header, vops):
    with open(path, 'wb') as f:
        f.write(header)
        for v in vops:
            f.write(v)


def deliver(stream, dst, fps, codec='prores'):
    """Decode an edited elementary stream and re-encode to a TD/Arena-safe codec. Returns codec actually used."""
    ext = os.path.splitext(dst)[1].lower()
    base = [FFMPEG, '-v', 'error', '-y', '-err_detect', 'ignore_err', '-fflags', '+genpts+discardcorrupt',
            '-f', 'm4v', '-framerate', str(fps), '-i', stream]
    if codec == 'hap' and 'hap' in run([FFMPEG, '-hide_banner', '-encoders'], False).stdout:
        run(base + ['-c:v', 'hap', '-format', 'hap', '-pix_fmt', 'rgb24', dst])
        return 'hap'
    if codec == 'hap':
        print('mosh: this ffmpeg has no hap encoder; writing ProRes instead (convert with TD Movie File Out / Arena)', file=sys.stderr)
        codec = 'prores'
    if codec == 'h264' or ext in ('.mp4',) and codec != 'prores':
        run(base + ['-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', dst])
        return 'h264'
    if ext not in ('.mov', '.mkv'):
        raise MoshError('ProRes needs a .mov output name (got %s)' % ext)
    run(base + ['-c:v', 'prores_ks', '-profile:v', '2', '-pix_fmt', 'yuv422p10le', '-vendor', 'apl0', dst])
    return 'prores'


# ---------- recipes (pure on vop lists) ----------
def drop_iframes(vops, keep_first=True):
    out, seen = [], False
    for v in vops:
        if vop_type(v) == 'I':
            if keep_first and not seen:
                seen = True
                out.append(v)
            continue
        out.append(v)
    return out


def bloom(vops, index, repeat):
    """Repeat the P-frame nearest to `index` `repeat` extra times. If index lands on an I-frame the next P is used."""
    index = max(0, min(index, len(vops) - 1))
    for j in range(index, len(vops)):
        if vop_type(vops[j]) == 'P':
            return vops[:j + 1] + [vops[j]] * repeat + vops[j + 1:]
    raise MoshError('no P-frame at/after index %d' % index)


def noise_bytes(data, header_len, amount, seed):
    """Flip one random bit per `amount` bytes of payload (header and first VOP start code left alone)."""
    rng = random.Random(seed)
    b = bytearray(data)
    lo = header_len + 64
    n = max(1, (len(b) - lo) // max(1, amount))
    for _ in range(n):
        b[rng.randrange(lo, len(b))] ^= 1 << rng.randrange(8)
    return bytes(b)


def transition_vops(a_vops, b_vops, a_keep=None):
    """A in full (its single I-frame leads), then B with its I-frames removed: B's motion drags A's last picture."""
    a = a_vops if a_keep is None else a_vops[:a_keep]
    return a + [v for v in b_vops if vop_type(v) != 'I']


# ---------- jobs ----------
def _check_out(out, force):
    if os.path.exists(out) and not force:
        raise MoshError('%s exists (use --force)' % out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)


def job_ifdrop(src, out, size=480, fps=30, cuts=(), cuts_frac=(), gop=100000, q=3, codec='prores', force=False,
               use_bsf=False, start=None, dur=None):
    _check_out(out, force)
    with tempfile.TemporaryDirectory() as td:
        if cuts_frac:
            total = dur or probe(src)['dur']
            cuts = list(cuts) + [f * total for f in cuts_frac]
        m4v = os.path.join(td, 'a.m4v')
        encode_m4v(src, m4v, size, fps, gop, q, cuts, start, dur)
        if use_bsf:  # ffmpeg-native route: drop every keyframe after the first
            m2 = os.path.join(td, 'b.m4v')
            run([FFMPEG, '-v', 'error', '-y', '-i', m4v, '-c', 'copy', '-bsf:v', r'noise=drop=gt(key\,0)*gt(n\,0)',
                 '-f', 'm4v', m2])
            stream = m2
        else:
            hdr, vops = split_vops(read_bytes(m4v))
            stream = os.path.join(td, 'b.m4v')
            write_stream(stream, hdr, drop_iframes(vops))
        return deliver(stream, out, fps, codec)


def job_bloom(src, out, at=None, at_frac=0.5, repeat=40, size=480, fps=30, q=3, codec='prores', force=False,
              start=None, dur=None):
    _check_out(out, force)
    with tempfile.TemporaryDirectory() as td:
        m4v = os.path.join(td, 'a.m4v')
        encode_m4v(src, m4v, size, fps, 100000, q, (), start, dur)
        hdr, vops = split_vops(read_bytes(m4v))
        idx = int(round(at * fps)) if at is not None else int(len(vops) * at_frac)
        stream = os.path.join(td, 'b.m4v')
        write_stream(stream, hdr, bloom(vops, max(1, idx), repeat))
        return deliver(stream, out, fps, codec)


def job_noise(src, out, amount=20000, seed=1, size=480, fps=30, q=3, codec='prores', force=False, start=None, dur=None):
    _check_out(out, force)
    with tempfile.TemporaryDirectory() as td:
        m4v = os.path.join(td, 'a.m4v')
        encode_m4v(src, m4v, size, fps, 100000, q, (), start, dur)
        data = read_bytes(m4v)
        hdr, _ = split_vops(data)
        stream = os.path.join(td, 'b.m4v')
        with open(stream, 'wb') as f:
            f.write(noise_bytes(data, len(hdr), amount, seed))
        return deliver(stream, out, fps, codec)


def job_transition(a, b, out, dur=2.0, size=480, fps=30, q=3, codec='prores', force=False, a_dur=None):
    """A (first a_dur seconds, default all) then B's P-frames only; B plays for `dur` seconds."""
    _check_out(out, force)
    with tempfile.TemporaryDirectory() as td:
        ma, mb = os.path.join(td, 'a.m4v'), os.path.join(td, 'b.m4v')
        encode_m4v(a, ma, size, fps, 100000, q, (), None, a_dur)
        encode_m4v(b, mb, size, fps, 100000, q, (), None, dur)
        ha, va = split_vops(read_bytes(ma))
        _, vb = split_vops(read_bytes(mb))
        stream = os.path.join(td, 'c.m4v')
        write_stream(stream, ha, transition_vops(va, vb))
        return deliver(stream, out, fps, codec)


def job_preset(name, src, out, b=None, **kw):
    if name not in PRESETS:
        raise MoshError('unknown preset %r (have: %s)' % (name, ', '.join(PRESETS)))
    _, mode, pk = PRESETS[name]
    kw = dict(kw)
    if mode == 'ifdrop':
        return job_ifdrop(src, out, **pk, **kw)
    if mode == 'bloom':
        return job_bloom(src, out, **pk, **kw)
    if mode == 'noise':
        return job_noise(src, out, **pk, **kw)
    if not b:
        raise MoshError('preset %s needs --b' % name)
    return job_transition(src, b, out, **kw)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p, io=True):
        if io:
            p.add_argument('src')
            p.add_argument('out')
        p.add_argument('--size', type=int, default=480, help='working width (px); output is this wide')
        p.add_argument('--fps', type=float, default=30)
        p.add_argument('--q', type=int, default=3, help='mpeg4 quality 1(best)-31')
        p.add_argument('--codec', choices=['prores', 'hap', 'h264'], default='prores')
        p.add_argument('--force', action='store_true')

    p = sub.add_parser('ifdrop'); common(p)
    p.add_argument('--cuts', default='', help='seconds, comma separated')
    p.add_argument('--gop', type=int, default=100000)
    p.add_argument('--bsf', action='store_true', help="use ffmpeg -bsf:v noise=drop instead of the Python VOP edit")
    p = sub.add_parser('bloom'); common(p)
    p.add_argument('--at', type=float, default=None, help='seconds'); p.add_argument('--repeat', type=int, default=40)
    p = sub.add_parser('noise'); common(p)
    p.add_argument('--amount', type=int, default=20000, help='one bit flip per N bytes'); p.add_argument('--seed', type=int, default=1)
    p = sub.add_parser('transition'); common(p, False)
    p.add_argument('a'); p.add_argument('b'); p.add_argument('out'); p.add_argument('--dur', type=float, default=2.0)
    p = sub.add_parser('preset'); common(p, False)
    p.add_argument('name'); p.add_argument('src', nargs='?'); p.add_argument('out', nargs='?'); p.add_argument('--b')
    sub.add_parser('presets')
    p = sub.add_parser('info'); p.add_argument('file')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'presets':
            for k, (d, _, _) in PRESETS.items():
                print('%-12s %s' % (k, d))
            return 0
        if a.cmd == 'info':
            print(probe(a.file)); return 0
        kw = dict(size=a.size, fps=a.fps, q=a.q, codec=a.codec, force=a.force)
        if a.cmd == 'ifdrop':
            cuts = [float(x) for x in a.cuts.split(',') if x]
            used = job_ifdrop(a.src, a.out, cuts=cuts, gop=a.gop, use_bsf=a.bsf, **kw)
        elif a.cmd == 'bloom':
            used = job_bloom(a.src, a.out, at=a.at, repeat=a.repeat, **kw)
        elif a.cmd == 'noise':
            used = job_noise(a.src, a.out, amount=a.amount, seed=a.seed, **kw)
        elif a.cmd == 'transition':
            used = job_transition(a.a, a.b, a.out, dur=a.dur, **kw)
        else:
            if not a.src or not a.out:
                raise MoshError('preset needs NAME IN OUT')
            used = job_preset(a.name, a.src, a.out, b=a.b, **kw)
        print('wrote %s (%s) %s' % (a.out if a.cmd != 'transition' else a.out, used, probe(a.out)))
        return 0
    except MoshError as e:
        print('mosh: %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
