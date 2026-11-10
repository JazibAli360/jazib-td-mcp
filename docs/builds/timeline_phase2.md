# TL_timeline phase 2: clips track (live v1 26 Oct 2026, TD 2025.31550, T-93; live checks 3, 8, 9 open)

Plan: `docs/builds/timeline_phases.md` (phase 2). COMP: `/project1/lab/TL_timeline`. Phase 1 stays as it was (same
builder, same 28 tests); phase 2 is added by the same `build()` call.

## Status
- **Offline: done.** Logic + 31 tests (`test/test_timeline_clips.py`, run together with phase 1:
  `python3 -I -m unittest discover -s test -p 'test_timeline*.py'` -> 59 OK). The runtime (`tl_clips`) was also
  smoke-run offline against fake ops (player files / indices / weights / ranks / strip drag as expected).
- **Live v1: done 26 Oct on 31550 (timeline_p2 lane, T-93).** Ticked: 1 (build clean, td_errors 0, layout ok, window
  open after build, no crash; rebuild-twice not run), 2 (play must be ON in specify mode - fixed in the builder; index
  exact), 4 (Seek 3.0 -> 0.498 = ffmpeg 127/255, Seek 2.0 -> 0.400 = 102/255), 5 (13.5 mid within 0.002 of TD's own
  red/blue mean), 6 partly (proxy: player CPU 0.81/0.56 vs full 1.19/0.82 ms, out 1080x1920; auto hitch not
  inspected), 7 (red preloaded at 9.50, first frame at 10.016 red), 10 (60.2 fps playing, window open; comp 0.14 CPU +
  0.40 GPU ms). **Open:** 3 (Maxplayers 3/4 + `tops`), 8 (clip-strip drags), 9 (Makeproxies pulse), rebuild-twice.
  Capture: the controls window shows ruler + lanes + clip strip (ramp/test/red/blue) + Clips page.

## Build (live lane, one exec, then td_errors + td_layout check)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/timeline.py').read(), ns)
ns['build']('/project1/lab')                 # clips=True is the default; panel=True only to regenerate sliders
```
Before it, offline (shell, not TD): `python3 -I tools/timeline_media.py --proxies media/demo/clips/*.mp4` (made
26 Oct: 4 sources, 4 All-Intra proxies, ~1.6 s). `build(..., clips=False)` = phase 1 only (program back to demo noise).

## Files
| File | What |
|---|---|
| `builders/timeline.py` | phase-1 builder; now `build(..., clips=True)` execs the phase-2 part, wires `program_src -> program`, keeps `controls/cliprow`; `tl_actions.tick` calls `tl_clips.tick(comp, t, jumped or held)` after the lanes (try/except: a clip error never stops the clock, message in storage `tl_clips_err`) |
| `builders/timeline_clips.py` | phase-2 builder part: runtime text `tl_clips`, compute composite, clip strip shader, pars, `build_clips`, `build_clip_panel` |
| `builders/timeline_clips_logic.py` | pure logic (copied into `tl_clips_logic`) |
| `tools/timeline_media.py` | ffprobe media info + All-Intra proxies, outside TD (threads, `--background`) |
| `test/test_timeline_clips.py` | 31 offline tests (logic, generated code compiles + ASCII, shader guards, media tool with ffmpeg) |
| `media/demo/clips/` | 4 synthetic test clips + `SOURCES.md` (git-ignored) |

## What it does
- **`clips` Table DAT**: `id track start dur src in speed fade proxy enabled` (any column order; `src` relative to the
  repo or absolute; `speed` 0 = freeze frame, negative = reverse; `proxy` empty = from media info, a path, or `none`).
  Edits by hand / `td_dat_text` / the clip strip. Seeded demo (reset or first build): ramp 0-6 s (in 2 s) -> test 5-10
  s (auto crossfade 5-6) -> red 10-14 -> blue 13-16 (crossfade 13-14, fade-out 15.5-16).
- **Weights** (`clip_weight`): own `fade` in/out at the edges; **same-track overlap = auto crossfade**: the later clip
  fades in over the whole overlap, the earlier stays at 1 under it, so with Blendmode over the midpoint is the exact
  mean. Other tracks layer (track 0 bottom, later start on top).
- **Player bank**: `player0..3` Movie File In, `playmode specify`, `indexunit indices`; index = floor(source time x
  movie fps) clamped to the last frame (frame-exact scrubbing). `Maxplayers` (1-4, default 2) players are wired into
  the composite (0-2 on connectors, player3 via `tops`); spares are unwired so they never cook. Assignment is stable
  (a clip keeps its player: no reload); free players **preload** clips starting within `Preroll` s (weight 0, index at
  their in point). Visible clips beyond Maxplayers drop from the bottom; `clip_status` says `dropped ... raise
  Maxplayers`.
- **Composite** `clips_comp`: ONE compute GLSL pass (T-46/T-47), 1080x1920 rgba8, uniforms `uW` (weights) / `uR` (rank
  per slot) written by `tl_clips.tick` only on change, `uMode` = Blendmode (over/add/screen), Premult (inputs straight
  -> premultiply), Fit (fit/fill/stretch), Maxplayers; every input access is behind `#if TD_NUM_2D_INPUTS > i`;
  `textureLod` (no implicit LOD in compute). Output is premultiplied. -> `clips_out` -> `program_src` (Switch, Program
  = clips / demo) -> `program` -> `program_out`.
- **Proxies**: `tools/timeline_media.py --proxies` writes `output/timeline/proxies/<key>/<name>_proxy.mp4` (H.264
  All-Intra `-g 1 -bf 0 -tune fastdecode`, half size, same fps + frame count, verified with ffprobe) and
  `output/timeline/media/<key>.json` ({src, fps, frames, w, h, dur, proxy}); key = sha1(abs path)[:16]. TD reads the json
  only when the clips table changes or on `Refreshmedia`. `Makeproxies` starts the tool with Popen (returns at once,
  log `output/timeline/media.log`) and polls the json once a second for 5 min. Sourcemode full / proxy / auto (proxy
  while the ruler is held, a seek jumped in the last 0.4 s, or a clip is dragged). Without media json: fps = the
  timeline's Fps, no end clamp.
- **Clip strip** (`controls/cliprow`, 1024x96 under the ruler): `clipview_data` (u0, u1, track, selected; recooks only
  on edits, playhead is a uniform) -> `clipview_tex` -> `clipstrip_draw` (ONE pixel pass, bounds-checked texelFetch)
  + `cliplabels` (ids) -> `clipview_out`. `clip_input`: click a bar = select (`Clip`), drag body = move (snapped,
  up/down changes track; one empty track row on top), drag within 6 px of an edge = trim (in edge slides the source in
  point, limited by source 0 / source end), click empty = seek. Rewriting the table keeps only the 10 standard columns.
- **Pars** (page Clips): Program, Maxplayers, Sourcemode, Blendmode, Premult, Fit, Preroll, Clip, Refreshmedia,
  Makeproxies; Info: Clipactive (ids on screen).

## Network (stages added to the phase-1 plan)
6 Clips: `tl_clips_logic`, `tl_clips`, `clips`, `clip_status`, `clips_pars`, `player0..3`, `clips_compute`,
`clips_comp`, `clips_out`, `program_src` | 7 Clip strip view: `clipview_data`, `clipview_tex`, `clipstrip_draw`,
`cliplabels_spec`, `cliplabels`, `clipview`, `clipview_out`, `clip_input`.

## LIVE CHECKs (do in order; record numbers here; every bug -> LEARNINGS T-nn)
Rules: park the other lab COMPs except ones a lane touched in the last minutes; un-park only TL_timeline; never change
cookRate (T-64); never numpyArray() a TOP in the exec that created/changed it, read >= 2 frames later (T-74).
1. **Build**: td_errors clean (GLSL compile of `clips_comp` compute + `clipstrip_draw`), `td_layout` check ok, panel
   window open: ruler + strip + sliders, no crash on rebuild with the window open (T-70). Rebuild twice: user clip rows kept.
2. **Movie File In facts** (unverified on 31550): `playmode specify` + `indexunit indices` shows frame `index` exactly;
   `par.file` write while not playing loads at once (how many frames until the new file shows?); default file
   (Banana.tif) in an unused player is harmless; whether an `interp` (frame blend) par must be off.
3. **Composite inputs**: TD_NUM_2D_INPUTS follows the wired count (Maxplayers 1/2/3) and `tops = player3` adds input 3
   for Maxplayers 4; the compute GLSL TOP accepts the `tops` par. If not: fall back to wiring 3 and capping at 3.
4. **Seek mid-clip = source frame**: Play off, Seek 3.0 (ramp only; source 5.0 s = frame 150) and Seek 2.0
   (frame 120): per-RGBA means of `clips_out` (centre crop) vs the ffmpeg
   frame within 1/255 (ramp grey per frame ~ 0.85/255; ffmpeg refs: frame 60 = 0.1922, 225 = 0.7412, 226 = 0.7451).
5. **Crossfade midpoint**: Seek 13.0 (red only) and 14.2 (blue only) read means, then 13.5: mean of both +-2%
   (ffmpeg refs red 0.7451 0.1843 0.1255, blue 0.1216 0.3098 0.8039 -> mid ~0.433 0.247 0.465; compare to TD's own
   red/blue readings, TD's YUV->RGB may differ from ffmpeg's).
6. **Proxy**: Sourcemode proxy lowers `td_perf` cook ms of the players (scrub with Stepfwd x30 and play), Out1 size
   stays 1080x1920; auto: proxy while scrubbing, full again 0.4 s after (watch for a reload hitch: black/stale frames
   when a player switches file; if so, keep the proxy until playback resumes, or use a separate proxy player).
7. **Preroll**: playing 9.0 -> 10.0 s, `red` is in a player before 10.0 (clip_status) and the cut at 10.0 shows red on
   the first frame (no black frame).
8. **Clip strip mouse** (real drags by hand or via the handler functions): select, move (snapped, track change),
   trim in/out; table rows updated; strip redraws only on edits (clipview_data 0 cooks/frame idle).
9. **Makeproxies** pulse from TD: Popen returns at once (no frame hitch), proxies appear, `Refreshmedia` picks them up.
   (`/usr/bin/python3` is used; fails gracefully into the log if absent.)
10. **Perf + fps** (window open, playing through both crossfades, Maxplayers 2): per frame tick (now incl. tl_clips),
    players, clips_comp GPU, strip; project at 60 fps (real frame times, T-73). Budget <= 3 ms for the COMP.

## Not in phase 2
Audio track, recording, markers export (phase 3); TimelineExt / agent API (phase 4); clip add/delete buttons (edit
the table); Hap proxies (H.264 All-Intra chosen: no extra codec, exact seeks; Hap later if decode cost needs it).
