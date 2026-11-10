"""TL_timeline phase 3 pure logic: offline record plan, offline audio mix (ffmpeg), marker + lane export.

No TD imports (tested offline: test/test_timeline_record.py). Copied into the COMP's `tl_record_logic` Text DAT and
imported by tools/timeline_render.py. Pure ASCII.

Recording model (docs/builds/timeline_phase3.md): the take steps the timeline's own clock t = in + k / cookRate on
TD frame k (realTime off, project cookRate never changed, T-64); a fresh Movie File Out writes by TD timeline time at
the file fps, so cooks = ceil(frames * cookRate / fps) and frames = ceil((out - in) * fps - eps). Audio is not taken
from TD's audio engine: it is mixed offline by ffmpeg from the same data (clips table + master file), sample-exact.
"""
import json
import math

EPS = 1e-6
SR = 48000
REC_CODECS = ('prores4444', 'prores422hq')
EXPORT_FORMATS = ('csv', 'json', 'ae')


def _f(x, default=0.0):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


# ---------------------------------------------------------------- record plan
def record_frames(t_in, t_out, fps):
    """Number of file frames for [in, out) at fps: ceil((out - in) * fps), float-safe (5 s at 60 = 300)."""
    span = _f(t_out) - _f(t_in)
    if span <= 0 or fps <= 0:
        return 0
    return int(math.ceil(span * fps - 1e-6))


def record_plan(t_in, t_out, fps, cook_rate):
    """{in, out, fps, frames, cooks, rate, step}. step = timeline seconds per TD frame during the take."""
    fps = _f(fps)
    rate = _f(cook_rate) or fps
    if fps <= 0:
        raise ValueError('fps must be > 0')
    n = record_frames(t_in, t_out, fps)
    if n < 1:
        raise ValueError('record range is empty (in %s, out %s)' % (t_in, t_out))
    cooks = int(math.ceil(n * rate / fps - 1e-9))
    return {'in': _f(t_in), 'out': _f(t_out), 'fps': fps, 'frames': n, 'cooks': cooks, 'rate': rate,
            'step': 1.0 / rate}


def take_time(plan, k):
    """Timeline time on TD frame k of the take (no accumulated float error)."""
    return plan['in'] + k * plan['step']


# ---------------------------------------------------------------- offline audio mix
def clip_fades(c, clips):
    """(fade in, fade out) seconds of a clip's audio = the same envelope as its picture (clip_weight)."""
    s, e = c['start'], c['start'] + c['dur']
    fi = fo = max(0.0, _f(c.get('fade')))
    for o in clips:
        if o is c or not o.get('enabled', True) or int(o.get('track', 0)) != int(c.get('track', 0)):
            continue
        os_, oe = o['start'], o['start'] + o['dur']
        if os_ < s - EPS and oe > s + EPS:
            fi = min(oe, e) - s
        if os_ > s + EPS and os_ < e - EPS:
            fo = 0.0
    return max(0.0, fi), max(0.0, fo)


def audio_segments(clips, has_audio, t_in, t_out, master=None, master_offset=0.0, master_gain=1.0, clip_gain=1.0):
    """Pieces of the mix inside [in, out): [{src, src_start, dur, at, fade_in, fade_out, fade_from, gain, id}].
    src_start = seconds into the source, at = seconds into the output, fades in output seconds relative to the
    piece start (fade_from = how far the piece starts into its clip's own envelope). has_audio(src) -> bool.
    Clips with speed != 1 are skipped (listed in 'skipped'). The master file plays at timeline time
    t = master_offset + file time."""
    segs, skipped = [], []
    t_in, t_out = _f(t_in), _f(t_out)
    for c in clips:
        if not c.get('enabled', True) or c['dur'] <= 0:
            continue
        if not has_audio(c['src']):
            continue
        if abs(_f(c.get('speed'), 1.0) - 1.0) > 1e-9:
            skipped.append(c['id'])
            continue
        s, e = c['start'], c['start'] + c['dur']
        a, b = max(s, t_in), min(e, t_out)
        if b - a <= EPS:
            continue
        fi, fo = clip_fades(c, clips)
        segs.append({'id': c['id'], 'src': c['src'], 'src_start': _f(c.get('in')) + (a - s), 'dur': b - a,
                     'at': a - t_in, 'clip_t0': a - s, 'clip_dur': c['dur'], 'fade_in': fi, 'fade_out': fo,
                     'gain': clip_gain})
    if master:
        mo = _f(master_offset)
        a = max(t_in, mo)
        if t_out - a > EPS:
            segs.append({'id': '__master__', 'src': master, 'src_start': a - mo, 'dur': t_out - a, 'at': a - t_in,
                         'clip_t0': 0.0, 'clip_dur': 0.0, 'fade_in': 0.0, 'fade_out': 0.0, 'gain': master_gain})
    return segs, skipped


def _env_expr(seg):
    """ffmpeg volume expression (t = seconds since the piece start) = clip_weight envelope x gain."""
    g = '%.6f' % seg['gain']
    if seg['fade_in'] <= EPS and seg['fade_out'] <= EPS:
        return g
    t0, dur = seg['clip_t0'], seg['clip_dur']
    parts = []
    if seg['fade_in'] > EPS:
        parts.append('(t+%.9f)/%.9f' % (t0, seg['fade_in']))
    if seg['fade_out'] > EPS:
        parts.append('(%.9f-(t+%.9f))/%.9f' % (dur, t0, seg['fade_out']))
    w = parts[0] if len(parts) == 1 else 'min(%s,%s)' % (parts[0], parts[1])
    return '%s*clip(%s,0,1)' % (g, w)


def mix_cmd(segs, total, out_wav, ffmpeg='ffmpeg', sr=SR):
    """ffmpeg argv: mix the pieces into a stereo pcm wav of exactly round(total * sr) samples."""
    n = int(round(_f(total) * sr))
    argv = [ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=%d:cl=stereo' % sr]
    chains, labels = [], ['[0:a]']
    for i, s in enumerate(segs):
        argv += ['-i', s['src']]
        k = i + 1
        lab = '[a%d]' % k
        ns = int(round(s['src_start'] * sr))
        nd = int(round(s['dur'] * sr))
        nat = int(round(s['at'] * sr))
        chains.append('[%d:a:0]aresample=%d,aformat=sample_fmts=fltp:channel_layouts=stereo,'
                      'atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS,volume=\'%s\':eval=frame,'
                      'adelay=delays=%dS:all=1%s' % (k, sr, ns, ns + nd, _env_expr(s), nat, lab))
        labels.append(lab)
    chains.append('%samix=inputs=%d:duration=longest:normalize=0,atrim=end_sample=%d,apad=whole_len=%d[out]'
                  % (''.join(labels), len(labels), n, n))
    argv += ['-filter_complex', ';'.join(chains), '-map', '[out]', '-c:a', 'pcm_s16le', '-ar', str(sr), out_wav]
    return argv


def mux_cmd(video, wav, out, ffmpeg='ffmpeg'):
    return [ffmpeg, '-v', 'error', '-y', '-i', video, '-i', wav, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
            '-c:a', 'pcm_s16le', '-shortest', out]


# ---------------------------------------------------------------- markers + lanes export
def markers_text(markers, fmt, fps=30.0, name='TL_timeline'):
    """markers [(time, name)] -> csv (time,frame,name) / json ({fps, markers:[{time, frame, name}]}) / ae (After
    Effects style: [{time, comment, duration, frame}])."""
    if fmt not in EXPORT_FORMATS:
        raise ValueError('format must be one of %s, got %r' % (EXPORT_FORMATS, fmt))
    ms = sorted((float(t), str(n)) for t, n in markers)
    fr = lambda t: int(math.floor(t * fps + 1e-4)) if fps > 0 else 0  # noqa: E731
    if fmt == 'csv':
        lines = ['time,frame,name']
        for t, n in ms:
            lines.append('%r,%d,"%s"' % (round(t, 9), fr(t), n.replace('"', "'")))
        return '\n'.join(lines) + '\n'
    if fmt == 'json':
        return json.dumps({'source': name, 'fps': fps, 'markers': [{'time': round(t, 9), 'frame': fr(t), 'name': n}
                                                                   for t, n in ms]}, indent=1)
    return json.dumps({'source': name, 'fps': fps, 'markers': [{'time': round(t, 9), 'comment': n, 'duration': 0.0,
                                                                 'frame': fr(t)} for t, n in ms]}, indent=1)


def parse_markers_text(text, fmt):
    """Inverse of markers_text -> [(time, name)] (round trip)."""
    if fmt == 'csv':
        out = []
        for ln in text.strip().splitlines()[1:]:
            t, _f_, n = ln.split(',', 2)
            out.append((float(t), n.strip().strip('"')))
        return out
    d = json.loads(text)
    key = 'name' if fmt == 'json' else 'comment'
    return [(float(m['time']), str(m[key])) for m in d.get('markers', [])]


def lanes_csv(names, value_fn, t_in, t_out, fps):
    """Per-frame lane values: header 'frame,time,<names>', rows for frames 0..record_frames-1, value_fn(name, t)."""
    n = record_frames(t_in, t_out, fps)
    lines = [','.join(['frame', 'time'] + ['"%s"' % x for x in names])]
    for k in range(n):
        t = _f(t_in) + k / float(fps)
        lines.append(','.join([str(k), repr(round(t, 9))] + [repr(round(float(value_fn(x, t)), 7)) for x in names]))
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- sync check helpers (tools/timeline_render.py)
def onsets(samples, sr, thresh=0.2, refractory=0.1):
    """Sample times (s) where |x| first crosses thresh, at least refractory s apart."""
    out, last = [], -1e9
    for i, v in enumerate(samples):
        if abs(v) >= thresh and (i - last) / float(sr) >= refractory:
            out.append(i / float(sr))
            last = i
    return out


def flash_frames(means, thresh=0.5):
    """Frame indices where a per-frame brightness (0..1) rises above thresh."""
    out, prev = [], False
    for i, m in enumerate(means):
        on = m >= thresh
        if on and not prev:
            out.append(i)
        prev = on
    return out


def pair_offsets(flash_times, click_times, max_gap=0.2):
    """[click - flash] for each flash with a click within max_gap (seconds)."""
    out = []
    for f in flash_times:
        best = None
        for c in click_times:
            if abs(c - f) <= max_gap and (best is None or abs(c - f) < abs(best)):
                best = c - f
        if best is not None:
            out.append(best)
    return out
