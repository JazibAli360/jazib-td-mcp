# TL_timeline phase 3: offline recording, audio track, marker export (built + verified live 26 Oct 2026, TD 2025.31550)

Plan: `docs/builds/timeline_phases.md` (phase 3). COMP: `/project1/lab/TL_timeline`. Same builder:
`build('/project1/lab')` now adds phase 3 (`record=True`, needs `clips=True`). LEARNINGS T-103.

## Files
| File | What |
|---|---|
| `builders/timeline_record.py` | builder part: pars (pages Record, Audio), runtime `tl_record`, `rec_pump`, `record_pars`, audio ops |
| `builders/timeline_record_logic.py` | pure logic (copied into `tl_record_logic`): record plan, offline mix argv, marker / lane export, sync helpers |
| `tools/timeline_render.py` | outside TD: `mux <plan.json>` (ffmpeg mix + mux + ffprobe report), `check <movie>` (flash vs click offsets) |
| `tools/timeline_media.py` | media json now has `audio` (has an audio stream) |
| `test/test_timeline_record.py` | 12 offline tests (with phase 1-2: 71 OK) |
| `media/demo/clips/tl_clickflash_60fps_6s.mov`, `media/demo/audio/tl_master_click_16s.wav` | synthetic sync media (SOURCES.md) |

## How it works
- **Record** (pulse): plan = `record_plan(Recin, Recout, Recfps, project.cookRate)` (Recout <= Recin = the loop range);
  frames = ceil((out - in) x fps), cooks = ceil(frames x cookRate / fps) (T-64; cookRate is read, never written). A
  fresh Movie File Out `rec_takeN` on program's input writes `<file>_video.mov`. `rec_pump` (frame end): 2 frames codec
  setup (menu filled at run time, same picker as offline_render), then Play off, realTime off, playhead held 10 frames at
  the in point (players load), then `tl_actions.tick` takes t = in + k / cookRate from `tl_record.clock()` (no float
  accumulation, sources forced full-res, no proxies) and the pump force-cooks the recorder once per frame. After the
  last cook: Record off, realTime + Seek restored, 15 frames to close the file, recorder removed (safe_destroy), plan
  json written, `timeline_render.py mux` started with Popen (no hitch). The mux mixes clip audio (clips with an audio
  stream and speed 1; envelope = the clip's picture weight incl. crossfades) + the master file into a 48 kHz stereo
  pcm track of exactly frames / fps seconds and muxes it (video copied); report `<file>.mov.report.json`
  (frames_counted vs expected). Recstatus shows `ok 300 frames -> <file>`. Recabort stops a take.
- **Audio track** (page Audio): `audio_master` (Audio File In, specify index in seconds = Seek - Audiooffset, gain
  Audiogain); `aclip0..3` follow the clip players' slots (index = source time, volume = weight x Clipgain; idle ones
  bypassed). `audio_mix` (Math add) -> `audio_null` -> `audio_out` (Out CHOP) and `audio_device` (Audio Device Out,
  device default = Mac speakers) active only while Play AND Listen AND not Recording; Listen is off by default. No
  audio input anywhere.
- **Export** (page Record): Exportmarkers (Exportformat csv: time,frame,name / json / ae: [{time, comment, duration,
  frame}]), Exportlanes (per-frame CSV of every lane over the record range at Recfps) -> `output/timeline/export/`;
  Lastexport shows the path.

## Live results (26 Oct, 31550)
- 0..5 s at 60 fps: ffprobe **300 / 300** frames, ProRes 4444 yuva444p12le 1080x1920, pcm 48 kHz stereo 240000 samples
  (5.000 s); take 8.0 s wall. Click/flash clip on the clips track + master click file (clicks at 0.25 + 0.5k):
  flashes at frames 0, 30, ..., 270; **A/V offset 21 us = 0.0013 frame** (clip clicks and master clicks).
- 1.1..3.1 s at 30 fps: **60 / 60** frames (120 cooks), flashes 12/27/42/57 (t = 1.5, 2.0, 2.5, 3.0), offset 0.0006 frame.
- Live audio: per frame the master/clip Audio File In slice ends at the playhead (click at 0.25 s at sample 793/800 of the
  frame with Seek 0.2504): locked to the clock within 1 ms; Audio Device Out adds its buffer (0.15 s).
- Listen: device active False (Play off), True (Play on), False again. Markers csv/json/ae round-trip equal; lanes CSV
  60 rows for 0..2 s at 30 fps, level at frame 45 (1.5 s) = 0.375 = lane_value.
- Phases 1-2 still: Seek 3.0 -> ramp index 150, demo_level 0.75 = lane_value; td_errors clean; layout check ok.
- Perf playing (pane elsewhere, other lanes cooking): **59.86 fps** (td_watch 5 s, one 37 fps sample); audio ops
  bypassed with the demo clips (no audio), tick + clock + lanes ~0.4 ms/frame.

## Open
Waveform row in the ruler view (not built); audio for clips with speed != 1 (skipped in the mix, listed); the Audio
Device Out buffer is not compensated (live listening only; takes are mixed offline).
