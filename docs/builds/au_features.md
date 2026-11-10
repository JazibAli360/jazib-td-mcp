# au_features - `/project1/lab/AU_features` (TD 2025.31550, 26 Oct 2026)

Audio features from the **EssentiaTD v2.0.3** C++ CHOPs (Rhythm, Loudness, Tonal, Spectral), loaded **by absolute
path** at runtime from `helpers/installs/disabled/Essentia/` (T-99), never from the per-user Plugins folder (T-81).
One clean Out CHOP of named channels for looks, the show rig and AC_audio.

**State:** built and verified on the **main TD** (plugins loaded there, Analysison on), then parked (allowCooking off).
The plugins stay loaded for the session (T-106: never unload). Turning it on: un-park the COMP; a fresh session pays
one 1.3-2.3 s stall per plugin on the first `Analysison` (staggered 30 frames apart) - do it before doors.

## Files
- `builders/au_features.py` - `build(parent_path='/project1/lab', name='AU_features', controls=True, analysis=None)`,
  idempotent: `g = dict(globals()); exec(open('<repo>/builders/au_features.py').read(), g); g['build']('/project1/lab')`
- `builders/au_features_logic.py` - pure logic (channel contract, BPM ranges + beat-clock BPM, key index, LUFS and
  centroid normalising, beat pulse, the known-answer test tracks). Copied into the COMP as `au_features_logic`.
- `builders/ac_audio_features.py` - `add()` / `remove()`: the optional Features merge in AC_audio (below).
- `test/test_au_features.py` - 21 offline tests: `python3 -I -m unittest discover -s test -p 'test_au_features.py'`.
- Test tracks (git-ignored, regenerate with `au_features_logic.write_test_tracks('media/demo/audio_tests')`):
  click_120bpm_30s, kick_128bpm_30s, kick_100bpm_30s_44k, tone_cmajor / tone_aminor / tone_gmajor_15s, sine_1000hz_10s.

## How it works
`file` (Audio File In, `Audiofile`) | `in1` (In CHOP) | `acaudio` (Select of `Acaudiopath`, default
`../AC_audio/n_mono`) -> `src_sel` (Source) -> `mono` (Math avg; Essentia is mono only) -> `n_in` -> `rhythm`,
`loudness`, `tonal`, `spectral` (CPlusPlus CHOPs, realtime) -> `features` (Script CHOP, callback `features_cb`) ->
`out_features` (Null) -> `out1` (Out CHOP). `pull` (Execute DAT) cooks `out_features` every frame while Analysison
and Alwayscook: without it only the viewer pulled the chain (~18 cooks/s), each cook got 2400+ samples, more than the
analysis window, and BPM read 83.7 for a 128 track.

Plugin pars bound after their first cook (`BINDS`): Rhythm realtime, Rtwindowsize **2048** (set by menu index, see
LEARNINGS T-109), Bpmmin/Bpmmax from Bpmrange, Onsetsensitivity, Onsetmethod; Tonal Keymode; Spectral mfcc/mel/hfc/
complexity off, centroid/flux/rolloff on.

## Channels (out1, 1 sample each)
| channel | meaning |
|---|---|
| `bpm` | beat-clock BPM: 60 / mean of the last 15 beat intervals (+-25 % of median), folded into the BPM range; falls back to `bpm_raw` until 5 beats (Bpmsource = beats; `essentia` = raw only) |
| `bpm_raw` | Essentia's bpm channel |
| `beat`, `beat_phase`, `beat_conf` | Rhythm beat tick, phase 0..1, confidence |
| `onset`, `onset_strength` | Rhythm onset tick + strength |
| `lufs`, `lufs_short`, `rms`, `zcr` | momentary / short-term loudness (LUFS, -144 = silence), RMS, zero-crossing rate |
| `centroid`, `flux`, `rolloff` | spectral centroid Hz, flux, rolloff Hz |
| `pitch`, `pitch_conf` | YinFFT pitch Hz + confidence |
| `key_minor`, `key_strength` | 0 major / 1 minor, key strength |
| `chroma_c` .. `chroma_b` | HPCP chroma, C first (12) |
| `beat_pulse` | 1 on a beat, exp decay over Beatdecay s |
| `loud` | lufs normalised 0..1 (Lufsfloor -> 0, 0 LUFS -> 1) |
| `centroid_norm` | centroid on a log scale 50 Hz..12 kHz -> 0..1 |
| `key_index` | 0..11, C = 0 (-1 = no key yet) |
| `beat_count`, `onset_count` | counters since Resetcounts |
| `live` | 1 while the analysers run |
| `bass`, `mid`, `high`, `band_level` | 28 Oct: 20-150 / 150-2000 / 2000-16000 Hz and full-band level, 0..1 on a dB scale (`Bandfloor` dBFS -> 0, a full-scale sine -> 1); from an FFT of `n_in` itself, so they also run with Analysison off (see Bands) |

## Pars
- **Features** (knobs): BPM range (wide 60-180 / slow / mid 70-110 / pop / house / fast / custom), BPM min/max,
  BPM from (beats / essentia), Onset sensitivity, Onset method, Beat pulse decay, Loud floor, Key mode (windowed /
  global), Reset counters, Band floor dBFS (`Bandfloor`, -60).
- **Setup**: Analysis on, Cook every frame, Source, Audio file, AC_audio mono CHOP, Essentia plugin folder,
  Re-init analysers (clears BPM/key history).

## Verified live (26 Oct, main TD pid 80442, other lanes cooking; plus scratch TD for the first plugin run)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- **BPM, click 120 (48 kHz):** `bpm` 120.00 from 18 s to 26 s, 119.73-121.08 from 14 s (+-1 from ~14 s); raw 120.0.
  Scratch (quiet TD): raw 120.00 at 10 s. **Kick 128:** `bpm` 127.66-128.88 from 8 s to 30 s, raw 127.27-128.57.
- **Onsets, click 120:** 52 in 26.1 s and 56 in 28.2 s (expected 2/s: 52.2 / 56.4); 47 in 23.8 s (47.6). Exact.
  The kick track gives ~4.7 onsets/s (kick + off-beat tick + kick pitch sweep), so onset checks use the click track.
- **Key:** C major tone -> key 0, G major -> 7, A minor -> 9 + minor 1 (switching key takes 10-17 s in windowed mode;
  global mode never leaves the first key without Re-init).
- **Centroid / loudness:** 1 kHz sine -> centroid 1090 Hz (+9 %, window leakage), RMS 0.4251 (theory 0.4243),
  LUFS -7.48.
- **Cost (pulled every frame, sum of ops cooked that frame, 181 frames):** median **1.10 ms**, p95 1.33, max 2.94
  (features Script CHOP 0.34, tonal 0.27, rhythm 0.14, spectral 0.12, file 0.10, loudness 0.09). td_watch 5 s:
  60.13 fps, 60.1 cooks/s.
- **Robustness:** stalls of 100-200 ms (other lanes, saves) give 4800-9600-sample timeslices, more than any analysis
  window: the analysers warn ("Window < input timeslice") and BPM wanders for a few seconds (raw 100-132 seen while
  the main TD stalled); the beat clock and the onset counts recover. Window 4096 was worse on the quiet scratch TD
  (123 BPM, extra onsets) - 2048 is the setting.

## Bands (28 Oct, for PX beat sync)
`n_in` is also wired to `features` input 4. `features_cb` keeps the latest 2048 samples (a ring of timeslices, module
global, not storage), applies a Hann window, and turns the one-sided power per band into an RMS by Parseval
(`au_features_logic.band_levels`; window + band masks cached per size / rate), then `db_norm` and a fast-attack /
0.12 s release (`band_smooth`). The Script CHOP sets `isTimeSlice = False` (the time-sliced input made `numSamples = 1`
warn every cook, T-244). Offline: sines at 70 Hz / 1 kHz / 6 kHz read 0.8997 in their band (0.5 amplitude), the others
< 0.70 (`test/test_px_phaseA.py` Bands). Live (b3): kick_128 bass 0.94 / mid 0.78 / high 0.10 on a kick; `features`
cook 0.47 -> 0.68 ms median (b3 under load; the whole AU chain 1.33 -> 1.53 ms).
Existing COMP: `bands_upgrade(parent_path, name)` (logic + callback text, Bandfloor par, the input-4 wire; no plugin
reload, Analysison untouched; second run `changed: []`), then zkit `refresh_panel`.

## AC_audio: optional Features merge
`builders/ac_audio_features.py add()` added to AC_audio (page Audio): `Features` (off) and `Featurespath`
(`../AU_features/out_features`); ops `feat_sel` -> `feat_merge` (out_ctl + features) -> `feat_gate` (off = out_ctl)
-> `out_ctl_feat`. No Out op added: an extra Out op would renumber the connectors LK_spectrum_glass uses. Checks on a
copy of AC_audio (file source, device + speaker off; the real AC_audio is parked with its device source): out_ctl
channels low/level/kick and ranges unchanged, spec_out 256x1, out_ctl_feat equal to out_ctl on all 19 samples with
Features on (40 channels: low level kick bpm ...), 3 channels equal to out_ctl with Features off, no errors. Real
AC_audio: output connectors (both -> LK_spectrum_glass) and out ops identical before/after, td_errors clean, still
parked, Features off.

## Open
- Per-song BPM range from the songmap (T-99: real songs read 1.5x with 60-180).
- Chroma/key on real songs and on the mic / BlackHole path (needs the user).
