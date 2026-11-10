# TL_timeline: build phases (26 Oct 2026, TD 2025.31550)

Spec: `docs/research/BD_rudiment_timeline.md` (clean-room, from twozero's one-line promise: "clips, keyframes,
proxies, recording and AI audio tools, fully open and agent-ready"). COMP: `/project1/lab/TL_timeline`.
Builder: `builders/timeline.py` (`build(parent_path)`, idempotent, keeps user table data); pure logic:
`builders/timeline_logic.py` (copied into the COMP's `tl_logic` Text DAT); tests: `test/test_timeline.py`.

Rules for every phase: own clock inside the COMP (never the project timeline, never `project.cookRate`, T-64);
custom pars drive everything; Outs carry output only; controls panel + window; staged layout; no safety limits; neutral
defaults; audio out = Mac speakers default only, never mic -> speaker.

## Phase 1: transport, clock, keyframe lanes, ruler UI (built 26 Oct)
Estimate 3 h (logic + tests 45 min, network 1 h, ruler GLSL + input 45 min, verify 30 min).
- **Clock**: `tick` Execute DAT (frame start) advances the playhead in Python (`advance()`): Play, Loop, Rate (-4..4),
  Inpoint/Outpoint, Length; `Clockmode` realtime (wall dt from `time.perf_counter`) or frame (1/Fps per TD frame, for
  phase 3 stepped renders). `Seek` is the playhead and the scrub input (a user write jumps the clock). Pulses: Gotostart,
  Gotoend, Stepback, Stepfwd (one frame, frame-snapped), Prevmarker/Nextmarker, Addmarker.
- **Grid / timecode**: Bpm, Beatsperbar, Snap + Snapdiv (beats/subdivisions, or frames), Tcmode seconds / frames /
  smpte (non-drop) / bars (bar.beat.sixteenth).
- **Lanes**: `lanes` Table DAT (name, op, par, min, max, enabled) -> one Table DAT `lane_<name>` per lane (time, value,
  interp). interp per key = shape of the segment that starts there: hold / linear / ease (smoothstep) / bezier (cubic
  Hermite, Catmull-Rom tangents, flat ends). Targets any parameter by op path (relative to the COMP or absolute).
  `lanes_eval` Script CHOP = one channel per lane; `tick` writes the bound pars (try/except per lane, constant-mode pars
  only; status in `lane_status`). Out CHOP `tl_out`: tl_time, tl_frame, tl_play, tl_beat, tl_bar, tl_wraps + lanes.
- **Ruler/lanes view**: `view_data` Script CHOP (curves sampled 512x per lane, key dots, markers) -> CHOP to TOP ->
  single-pass GLSL `ruler_draw` (ruler, bar/beat grid, loop region, markers, lane curves, key dots, playhead) + Text TOP
  labels (spec DAT) -> `view`. Panel `controls/ruler` with `ruler_input` Panel Execute: click ruler strip = scrub, drag
  a key = move (snapped), right-click empty lane = add key, right-click key = delete. Buttons: Addkey (at playhead,
  Keyvalue, Keyinterp, lane `Lane`), Deletekey, Prevkey, Nextkey.
- **Acceptance**: offline tests pass; td_errors clean; layout check ok; lane values at given times match the maths within
  1e-3; loop wraps (t stays in [in, out], wrap counter rises); Rate 2 halves the wall time of a pass; td_perf on the COMP.

### Phase 1 result (verified live 26 Oct, TD 2025.31550, after the crash recovery)
- Builder made T-70 safe: no direct `.destroy()` (wrong-type ops go through `safe_destroy`), `build()` closes the COMP's
  own `controls_window` first, `controls` / `ruler` / `params` are kept and updated in place; slider widgets are
  regenerated only when missing or `build(..., panel=True)` (old ones via `safe_destroy`). The builder never moves the
  network pane. Rebuild with the window open and `panel=True`: window closed, 24 widgets remade, no errors.
- Offline: 28 tests pass (`test/test_timeline.py`).
- Lanes: at t = 2 / 5 / 9.5 / 13 s, `lanes_eval` and the driven pars (`demo_level.value0`, `demo_noise.tx`) equal
  `lane_value()` exactly (e.g. level 0.5 / 0.8828 ease / 0.25 hold / 0.5625); an absolute-path target
  (`/project1/lab/TL_timeline/demo_noise.ty`) driven (0.25 at t = 4 of 0->1 over 16 s); a bad target reports
  `missing op` in `lane_status` and the clock keeps running.
- Clock: Rate 1, 6.1659 s wall -> tl_time 6.1662 (ratio 1.00005); Loop off stops at Outpoint 4.0 and turns Play off;
  Loop on 2..4 s at Rate 2: 11 wraps in 11.47 s wall (expected 11.47), playhead 2.9413 = 2 + (2 x 11.47 mod 2).
- Pulses: Stepfwd 5 -> 5.0333 (1/30), Stepback x2 -> 4.9667, Nextmarker -> 8, Prevkey -> 4, Gotoend -> 16; Addkey /
  Deletekey change `lane_level` 6 -> 7 -> 6 rows, value at the new key = Keyvalue 0.9.
- Ruler mouse (handler functions): right-click empty lane = add key (t snapped to beat 6.0), right-click on it = delete,
  left press/drag on the ruler = scrub (u 0.25 -> 4.0 s). `view_data` recooks once per key edit (0 cooks/frame idle).
- Perf (window open, playing): 59.9 fps; per frame tick 0.022 ms, clock 0.07, lanes_eval 0.18, ruler_draw 0.24
  (1 cook/frame), labels 0.24 (0.55 cooks/frame, only when the text changes): about 0.8 ms CPU/frame.
- Not yet done in phase 1: a real mouse drag in the window was tested through the handler functions, not by hand;
  the Setup page (Length, Fps, Bpm, Snap...) is not in the panel (set-once pars, panel would exceed ~1000 px).

## Phase 2: clips (offline prep done 26 Oct, live checks pending; estimate 3.5 h)
Prepared offline: `docs/builds/timeline_phase2.md` (what was built, files, LIVE CHECK list). Plan as written:
- `clips` Table DAT (id, track, start, dur, src, in, speed, fade, proxy, enabled); `active_clips()` pure logic (tested).
- Fixed bank of 4 Movie File In TOPs (`playmode` specify index, index = local time * movie fps; scrubbing exact),
  `Maxplayers` (default 2 full-res), spare players off.
- Single compute-mode GLSL composite (T-46/T-47) with weights from crossfades; Blendmode over/add/screen; Premult.
- Proxies: `<name>_proxy.mp4` (All-Intra H.264 or Hap) made by ffmpeg from the MCP/offline side in the background
  (never inside TD's cook); Sourcemode full / proxy / auto (proxy while scrubbing).
- Clip bars in the ruler view (a clip track row), drag to move/trim if the phase-1 input proves solid.
- Acceptance: seek mid-clip = source frame (per-RGBA means within 1/255); crossfade midpoint = mean of both +-2%;
  proxy lowers td_perf cook time, Out1 size unchanged.

## Phase 3: recording, audio track, markers export (built + verified live 26 Oct: docs/builds/timeline_phase3.md)
Result: 5 s at 60 fps -> 300/300 frames (ffprobe), A/V offset 0.0013 frame vs a click track, markers round-trip;
the take steps its own clock (in + k / cookRate) instead of `Clockmode frame`, and audio is mixed offline by ffmpeg.
Plan as written:
- Offline stepped render reusing `offline_render` / `td_render_for_ae` patterns: fresh Movie File Out per take, force
  cook each frame, `Clockmode frame` so the timeline steps exactly 1/Fps per pumped frame; **never change cookRate live
  (T-64)**; pump frames*cookRate/fps; ffprobe count = ceil((out-in)*fps). realTime off for big frames (T-11), restored.
- Lane CSV export (per-frame values) and markers export (csv / json; AE-style marker json for `td_export_ae_data`).
- Audio track: Audio File In CHOP locked to the clock (cue = tl_time), muted by default; listen path only to the Mac
  speakers default device; waveform row in the ruler view.
- Acceptance: 2 s at 30 fps -> 60 frames; first/last frames equal the live seeks; markers round-trip.

## Phase 4: AI audio tools + agent-ready API (estimate 2.5 h, local only)
**Agent API: offline prep done 26 Oct** (`docs/builds/timeline_phase4.md`: TimelineExt, tl_api_logic, handlers
`timeline_*`, MCP `td_timeline_*` state/show/edit/transport/export/load/record, 35 offline tests, LIVE CHECK list).
Record + lane CSV / markers export from phase 3 are covered there (stepped take via offline_render); the audio track
and the AI audio tools below are still open.
- Python extension `TimelineExt` on the COMP: Play/Pause/Stop/Seek/AddKey/DeleteKey/MoveKey/AddLane/BindLane/
  AddMarker/AddClip/Export... (wrapping the phase-1 `tl_actions` functions).
- MCP-facing command list (for later typed tools, e.g. `td_timeline {comp, action, ...}`): list in this file + PROTOCOL
  draft; agents edit tables through `td_dat_text` already.
- Local audio tools (no cloud/paid): onset/beat lane from audiospectrum/analyze CHOPs, beat -> markers, BPM estimate
  (offline librosa-free autocorrelation in pure Python, tested); stems/transcription stay out (cloud in the original).
- Acceptance: each extension method covered by an offline test of its logic + a live call; beat markers on a click
  track within 1 frame.
