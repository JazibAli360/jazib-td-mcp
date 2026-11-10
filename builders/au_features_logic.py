"""au_features logic: pure Python (stdlib only, no td), copied into AU_features/au_features_logic as a Text DAT module.

EssentiaTD v2.0.3 CHOPs (LEARNINGS T-99) give raw channels; this module names, orders and normalises them, picks the
BPM range, maps key labels to indices, and writes the known-answer test tracks (click / kick / tone) with `wave`.
Channel facts read live on 31550 (scratch TD, 26 Oct): Rhythm onset onset_strength bpm beat beat_phase
beat_confidence; Loudness loudness loudness_momentary loudness_shortterm loudness_integrated dynamic_range rms zcr;
Tonal pitch pitch_confidence note_a note_as ... note_gs key major_minor key_strength dissonance inharmonicity;
Spectral spectral_centroid (+ flux / rolloff when enabled, mfcc/mel/hfc/complexity switched off here).
Pure ASCII.
"""
import math
import struct
import wave

ESSENTIA_DIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/installs/disabled/Essentia/'
PLUGINS = ('Rhythm', 'Loudness', 'Tonal', 'Spectral')

# pitch classes, C first (index 0 = C ... 11 = B)
PITCH = ('c', 'cs', 'd', 'ds', 'e', 'f', 'fs', 'g', 'gs', 'a', 'as', 'b')
PITCH_LABEL = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
FLATS = {'DB': 'C#', 'EB': 'D#', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#', 'CB': 'B', 'FB': 'E', 'E#': 'F', 'B#': 'C'}

# BPM ranges (T-99: a real song read 1.5x with 60-180; the range per song fixes the metre)
BPM_RANGES = (('wide', 'Wide 60-180', 60, 180), ('slow', 'Slow 60-100', 60, 100), ('mid', 'Mid 70-110', 70, 110),
              ('pop', 'Pop 90-130', 90, 130), ('house', 'House 110-140', 110, 140), ('fast', 'Fast 130-180', 130, 180),
              ('custom', 'Custom (Bpmmin/Bpmmax)', None, None))

SOURCES = (('file', 'Audio file (Audiofile)'), ('input', 'In CHOP (in1)'), ('acaudio', 'AC_audio mono (n_mono)'))

# (output name, source op, source channel) -- the clean Out CHOP contract
CHANNELS = (
    ('bpm_raw', 'rhythm', 'bpm'), ('beat', 'rhythm', 'beat'), ('beat_phase', 'rhythm', 'beat_phase'),
    ('beat_conf', 'rhythm', 'beat_confidence'), ('onset', 'rhythm', 'onset'),
    ('onset_strength', 'rhythm', 'onset_strength'),
    ('lufs', 'loudness', 'loudness_momentary'), ('lufs_short', 'loudness', 'loudness_shortterm'),
    ('rms', 'loudness', 'rms'), ('zcr', 'loudness', 'zcr'),
    ('centroid', 'spectral', 'spectral_centroid'), ('flux', 'spectral', 'spectral_flux'),
    ('rolloff', 'spectral', 'spectral_rolloff'),
    ('pitch', 'tonal', 'pitch'), ('pitch_conf', 'tonal', 'pitch_confidence'),
    ('key_raw', 'tonal', 'key'), ('key_minor', 'tonal', 'major_minor'), ('key_strength', 'tonal', 'key_strength'),
) + tuple(('chroma_' + p, 'tonal', 'note_' + p) for p in PITCH)

DERIVED = ('bpm', 'beat_pulse', 'loud', 'centroid_norm', 'key_index', 'beat_count', 'onset_count', 'live')

# 28 Oct (PX beat sync): three bands + a full-band level from the mono audio itself (numpy FFT in the features Script
# CHOP; no Essentia needed, so they also run with Analysison off). 0..1 on a dB scale: Bandfloor dBFS -> 0, a
# full-scale sine in the band -> 1.
BANDS = (('bass', 20.0, 150.0), ('mid', 150.0, 2000.0), ('high', 2000.0, 16000.0))
BAND_CHANNELS = tuple(b[0] for b in BANDS) + ('band_level',)
BAND_N = 2048                                   # analysis window (samples, ring of the latest timeslices)
BAND_FLOOR = -60.0
BAND_RELEASE = 0.12                             # s: fast attack, exponential release (smooth between frames)

LUFS_FLOOR = -60.0
CENTROID_LO, CENTROID_HI = 50.0, 12000.0


def menu_index(menu, name, default=0):
    for k, m in enumerate(menu):
        if m[0] == name:
            return k
    return default


def bpm_range(name, bmin=60.0, bmax=180.0):
    """(min, max) for a BPM range name; 'custom' (or unknown) uses bmin/bmax, ordered, at least 10 BPM apart."""
    for n, _label, lo, hi in BPM_RANGES:
        if n == name and lo is not None:
            return float(lo), float(hi)
    lo, hi = sorted((float(bmin), float(bmax)))
    lo = max(30.0, lo)
    return lo, max(hi, lo + 10.0)


def loud_norm(lufs, floor=LUFS_FLOOR):
    """LUFS (momentary) -> 0..1: floor dB -> 0, 0 dB -> 1. Essentia reports -144 for silence."""
    try:
        x = float(lufs)
    except (TypeError, ValueError):
        return 0.0
    if x != x:
        return 0.0
    return max(0.0, min(1.0, (x - floor) / -floor))


def db_norm(rms, floor=BAND_FLOOR):
    """RMS -> 0..1: dB of a sine's peak (rms x sqrt 2), floor -> 0, 0 dBFS -> 1."""
    if not rms > 0:
        return 0.0
    db = 20.0 * math.log10(rms * math.sqrt(2.0))
    return max(0.0, min(1.0, (db - floor) / -floor))


def band_levels(samples, rate, floor=BAND_FLOOR, bands=BANDS, cache=None):
    """Mono samples (the latest BAND_N) -> {bass, mid, high, band_level} in 0..1. Hann window, one-sided power per
    band by Parseval: rms_band^2 = 2 sum |X_k|^2 / (N sum w^2), so a sine of amplitude A in a band reads rms A/sqrt 2
    there (-> 0 dB at full scale). numpy is imported here (TD has it; the rest of this module is stdlib only)."""
    import numpy as np
    x = np.asarray(samples, dtype=np.float64).ravel()
    out = dict((b[0], 0.0) for b in bands)
    out['band_level'] = 0.0
    n = x.size
    if n < 16 or not rate or rate <= 0:
        return out
    key = (n, float(rate), tuple(bands))
    if cache is not None and cache.get('key') == key:          # window + band masks cached per (size, rate):
        w, k, masks = cache['w'], cache['k'], cache['masks']    # each cook runs only the FFT
    else:
        w = np.hanning(n)
        k = 2.0 / (n * float(np.sum(w * w)))
        f = np.fft.rfftfreq(n, 1.0 / float(rate))
        masks = [(name, (f >= lo) & (f < hi)) for name, lo, hi in bands]
        if cache is not None:
            cache.update({'key': key, 'w': w, 'k': k, 'masks': masks})
    X = np.fft.rfft(x * w)
    p = (X.real * X.real + X.imag * X.imag) * k
    p[0] *= 0.5                                  # DC is not doubled
    for name, m in masks:
        out[name] = db_norm(math.sqrt(float(np.sum(p[m]))), floor)
    out['band_level'] = db_norm(math.sqrt(float(np.sum(p[1:]))), floor)
    return out


def band_smooth(prev, new, dt, release=BAND_RELEASE):
    """Fast attack, exponential release: max(new, prev x exp(-dt / release))."""
    if prev is None:
        return new
    k = math.exp(-max(dt, 0.0) / release) if release > 0 else 0.0
    return max(new, prev * k)


def centroid_norm(hz, lo=CENTROID_LO, hi=CENTROID_HI):
    """Spectral centroid Hz -> 0..1 on a log scale (lo..hi Hz)."""
    try:
        x = float(hz)
    except (TypeError, ValueError):
        return 0.0
    if not x > 0:
        return 0.0
    return max(0.0, min(1.0, math.log(max(x, lo) / lo) / math.log(hi / lo)))


def key_index_from_label(label):
    """'C' / 'c#' / 'Bb' / 'A minor' -> 0..11 (C = 0); None when not a key."""
    if label is None:
        return None
    s = str(label).strip().split()[0].upper() if str(label).strip() else ''
    s = FLATS.get(s, s)
    return PITCH_LABEL.index(s) if s in PITCH_LABEL else None


def key_index_from_raw(raw, base=0):
    """Tonal's numeric `key` channel -> 0..11 with C = 0. `base` = the pitch class the plugin calls 0 (checked live
    with a C-major tone track; see docs/builds/au_features.md). Negative / NaN -> -1 (no key yet)."""
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return -1
    if x != x or x < 0:
        return -1
    return (int(round(x)) + int(base)) % 12


def key_name(idx, minor=0):
    if idx is None or idx < 0:
        return '-'
    return PITCH_LABEL[int(idx) % 12] + (' minor' if minor and float(minor) >= 0.5 else ' major')


def chroma_argmax(vals):
    """Index (C = 0) of the strongest chroma bin, -1 if all are 0."""
    best, bi = 0.0, -1
    for i, v in enumerate(vals):
        if v > best:
            best, bi = v, i
    return bi


def pulse_decay(frames_since_beat, decay_s, fps=60.0):
    """Beat pulse envelope: 1 on the beat frame, exp decay to ~0.05 after decay_s."""
    if frames_since_beat is None or frames_since_beat < 0:
        return 0.0
    if decay_s <= 0:
        return 1.0 if frames_since_beat == 0 else 0.0
    return math.exp(-3.0 * (frames_since_beat / float(fps)) / decay_s)


def fold_bpm(bpm, lo, hi):
    """Double / halve bpm into [lo, hi] (metre folding); unchanged if it cannot fit."""
    if not bpm or bpm <= 0:
        return 0.0
    b = float(bpm)
    for _ in range(4):
        if b < lo:
            b *= 2.0
        elif b > hi:
            b /= 2.0
    return b if lo <= b <= hi else float(bpm)


def bpm_from_beats(times, lo=60.0, hi=180.0, max_n=16, min_n=5):
    """Stable BPM from the last beat times (seconds): intervals within +-25 % of their median are kept, BPM =
    60 / mean(kept), folded into [lo, hi]. Live 31550 (main TD, other lanes cooking): Essentia's own bpm channel
    wandered 108-120 on a 120 click while its beat channel ticked exactly every 0.5 s; the beat clock is the
    reliable part. Frame-quantised times (16.7 ms) average out over 15 intervals (< 0.5 BPM). 0 when too few."""
    t = list(times)[-max_n:]
    if len(t) < min_n:
        return 0.0
    iv = sorted(b - a for a, b in zip(t, t[1:]) if b > a)
    if not iv:
        return 0.0
    med = iv[len(iv) // 2]
    keep = [x for x in iv if 0.75 * med <= x <= 1.25 * med]
    if len(keep) < min_n - 1:
        return 0.0
    return fold_bpm(60.0 / (sum(keep) / len(keep)), lo, hi)


def rising_edges(samples, thresh=0.5):
    """Number of rising edges through thresh (counting onsets / beats in a recorded channel)."""
    n, prev = 0, None
    for v in samples:
        hi = v >= thresh
        if hi and prev is False:
            n += 1
        prev = hi
    return n


def bpm_ok(measured, true_bpm, tol=1.0):
    return measured is not None and abs(float(measured) - float(true_bpm)) <= tol


# ---- known-answer test tracks (stdlib wave, 16-bit mono) -------------------------------------------------------

def _write(path, samples, rate):
    w = wave.open(path, 'wb')
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(b''.join(struct.pack('<h', int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    finally:
        w.close()
    return path


def click_times(bpm, seconds, offset=0.25):
    step = 60.0 / float(bpm)
    t, out = float(offset), []
    while t < seconds - 0.05:
        out.append(round(t, 6))
        t += step
    return out


def click_track(bpm, seconds, rate=48000, offset=0.25, click_ms=8.0, freq=2000.0, amp=0.8):
    """Silence with a short decaying sine burst on every beat. Returns (samples, click times)."""
    n = int(seconds * rate)
    s = [0.0] * n
    times = click_times(bpm, seconds, offset)
    cl = int(rate * click_ms / 1000.0)
    for t in times:
        i0 = int(round(t * rate))
        for k in range(cl):
            if i0 + k >= n:
                break
            s[i0 + k] = amp * math.exp(-5.0 * k / cl) * math.sin(2 * math.pi * freq * k / rate)
    return s, times


def kick_track(bpm, seconds, rate=48000, offset=0.25):
    """Four-on-the-floor: 55 Hz pitch-dropping kick on beats + a short noise-free 6 kHz tick on the off-beats."""
    n = int(seconds * rate)
    s = [0.0] * n
    times = click_times(bpm, seconds, offset)
    step = 60.0 / bpm
    kl = int(0.18 * rate)
    hl = int(0.02 * rate)
    for t in times:
        i0 = int(round(t * rate))
        ph = 0.0
        for k in range(kl):
            if i0 + k >= n:
                break
            f = 55.0 + 90.0 * math.exp(-k / (0.02 * rate))
            ph += 2 * math.pi * f / rate
            s[i0 + k] += 0.9 * math.exp(-k / (0.06 * rate)) * math.sin(ph)
        j0 = int(round((t + step / 2) * rate))
        for k in range(hl):
            if j0 + k >= n:
                break
            s[j0 + k] += 0.25 * math.exp(-k / (0.004 * rate)) * math.sin(2 * math.pi * 6000.0 * k / rate)
    return s, times


def tone_track(freqs, seconds, rate=48000, amp=0.6):
    """Sum of sines (equal level, normalised) -- C major triad for key, 1 kHz alone for the centroid."""
    n = int(seconds * rate)
    a = amp / max(1, len(freqs))
    w = [2 * math.pi * f / rate for f in freqs]
    return [a * sum(math.sin(x * i) for x in w) for i in range(n)]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


C_MAJOR = tuple(midi_hz(m) for m in (48, 52, 55, 60, 64, 67, 72))      # C3 E3 G3 C4 E4 G4 C5
A_MINOR = tuple(midi_hz(m) for m in (45, 48, 52, 57, 60, 64, 69))      # A2 C3 E3 A3 C4 E4 A4


def write_test_tracks(folder, rate=48000):
    """Writes the known-answer tracks; returns {name: (path, facts)}."""
    import os
    os.makedirs(folder, exist_ok=True)
    out = {}
    s, t = click_track(120, 30, rate)
    out['click120'] = (_write(os.path.join(folder, 'click_120bpm_30s.wav'), s, rate), {'bpm': 120, 'clicks': len(t)})
    s, t = kick_track(128, 30, rate)
    out['kick128'] = (_write(os.path.join(folder, 'kick_128bpm_30s.wav'), s, rate), {'bpm': 128, 'kicks': len(t)})
    s, t = kick_track(100, 30, 44100)
    out['kick100'] = (_write(os.path.join(folder, 'kick_100bpm_30s_44k.wav'), s, 44100), {'bpm': 100})
    out['cmajor'] = (_write(os.path.join(folder, 'tone_cmajor_15s.wav'), tone_track(C_MAJOR, 15, rate), rate),
                     {'key': 'C major', 'key_index': 0})
    out['aminor'] = (_write(os.path.join(folder, 'tone_aminor_15s.wav'), tone_track(A_MINOR, 15, rate), rate),
                     {'key': 'A minor', 'key_index': 9})
    out['sine1k'] = (_write(os.path.join(folder, 'sine_1000hz_10s.wav'), tone_track((1000.0,), 10, rate), rate),
                     {'centroid_hz': 1000})
    return out
