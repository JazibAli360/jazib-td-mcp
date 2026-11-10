# AI - TouchDesigner <-> Resolume Arena (integration research, 26 Oct 2026)

Brief: `INTEGRATION_BRIEF.md`. Research only: no TD call, no Arena call, no MCP call, nothing installed or started. I read
files on this Mac (TD's offline help, Arena's installed help, Arena's own prefs XML read-only, `mcp-vendor/resolume-mcp-server/`),
and the bundle docs. Target: TD 2025.31550 (macOS, Rosetta, Pro), show host Arena **7.23.2 (51094)** via `resolume-723`;
official server `resolume-arena` for 7.26+.
Tags: **[V]** read in a doc/file named in Sources; **[S]** secondary (third-party repo claim, forum snippet, author's live test
we did not repeat); **[U]** unverified / my inference / needs a test; **[D]** op or par confirmed in `ops/` dump. The Syphon, NDI,
OSC, MIDI, Web Client ops are **not in the dump** (`skipped_not_created`: they open ports/devices), so their pars are [V] from TD's
offline help only, never [D]; Ableton Link CHOP, Timecode CHOP, Movie File Out TOP, Beat CHOP are [D].

## Summary
1. **Video TD -> Arena:** Syphon Spout Out TOP (same Mac, 8-bit RGBA, [V]) or NDI Out TOP (network, 8/16-bit, optional alpha, [V]).
   Arena lists both under Sources and drags them into a clip like a camera [V Arena help]. Neither has been run between this
   Rosetta TD and Arena (E). `td_publish` (proposed) builds the sender chain with the right name/format and tells you what to pick.
2. **Alpha is the trap.** Arena's clip setting "Alpha Type" defaults to Premultiplied ("usually the way to go; halos -> Straight",
   [V] installed help). Syphon's alpha meaning is undocumented by TD; NDI's is [U]. Rule (memory `overlay-alpha-premultiplied`):
   premultiplied out, verified with Arena's own blend, "not checked in Arena" until it has been. For live looks the safe path is
   still **Add blend, no alpha needed** (E 6).
3. **Arena -> TD:** state via REST (`GET /api/v1/composition`, Web Client DAT) or push via the WebSocket; events/params via Arena's
   OSC Output into an OSC In DAT; video back via Arena's Syphon/NDI outputs (beware the feedback loop, Patterns 5).
4. **OSC addresses are per build.** Arena's prefs on this Mac: OSC Input **disabled**, port 7000; OSC Output **disabled**, target
   127.0.0.1:7001 [V file `osc.xml`]. Method = the old repo's `learn` (passive sniff) redone as a TD OSC In logger; map = starting
   point, not gospel. Live-checked on 7.23.2 by the resolume-723 author: tempo over OSC is **normalised 0..1**, not BPM [S].
5. **Tempo:** Arena owns it (or Ableton via Link). TD's Link CHOP is **listen-only** [V]; Arena help shows Link toggle, Tap,
   Resync, SMPTE inputs and **no MIDI-clock input** [V help, absence only]. TD follows Arena by Link, or by REST/OSC readback.
6. **Clips:** TD makes ProRes/Hap/image sequences, **no DXV** (T-11); DXV3 = Resolume Alley command line (H-36). Hap Q is the one
   codec TD writes that Arena plays natively [S]; neither is tested here at 7488x2880 in Arena.
7. **What `resolume-723`'s 37 tools do** once a TD source sits in a clip: trigger, layer opacity/bypass/blend, effects, BPM, OSC send.
   They **cannot add a Syphon/NDI source to a clip** (no open-clip tool); the user drags it in (Existing 5).
8. **Proposed:** `td_publish` (the helper), `td_publish_status`, `td_arena_link` (OSC/REST/clock recipes as a typed tool),
   `td_clip_bake` (offline render + frame-count check). All build-gated, one structural change per call, dry-run before any send.

## Existing
### 1. TD built-ins (what is on the Mac)
| Item | Facts | Tag |
|---|---|---|
| Syphon Spout Out TOP `syphonspoutoutTOP` | pars `active`, `sendername` (any text); "Syphon is limited to 8-bit RGBA"; shared memory, same computer only; no size limit stated; alpha handling not described | [V] help `Syphon_Spout_Out_TOP.htm` |
| Syphon Spout In TOP | `sendername`; Resolume -> TD | [V] E, TOP.md 2.8 |
| NDI Out TOP `ndioutTOP` | `active`, `name`, `failovername` (`MACHINENAME (SourceName)`), `fps` (compression guide: higher fps = more compressed), `lowperformancebehavior` (`stallmainthread`/`skipframes`), `outputpixelformat` (`fixed8`/`fixed16`), `includealpha` (off = alpha 1.0), `grouptable`, `audiochop`, `metadata`; Info CHOP `last_send_time`, `skipped_frames` | [V] help `NDI_Out_TOP.htm`, X |
| NDI In TOP / NDI DAT | `name`, `extraips`, `bandwidth`; NDI DAT lists sources by name, callbacks on add/remove | [V] DAT.md, TOP.md |
| NDI SDK | TD `libndi` 6.2.0.3; Arena folder `libndi.dylib` 6.1.1 (both universal) | [V] E 3, T-43 |
| OSC In/Out CHOP + DAT | OSC Out DAT `sendOSC(address, *values, asBundle=False, ...)`; OSC In DAT table + Callbacks DAT, protocol UDP/multicast, address scope, `Clamp`/`Max Lines` (FIFO default cap) | [V] DAT.md 150/151, help |
| Web Client DAT / WebSocket DAT | HTTP GET/PUT/POST and WS client; our own bridge already uses a WebSocket DAT dialling out on this Mac (AUDIT) | [V]/[S] |
| Ableton Link CHOP `abletonlinkCHOP` | pars `active`, `enable`, `startstopsync`, `signature1/2`, `callbacks`; outputs `status`(numpeers, linked, waiting, synced) `ramp pulse sine count bar beat sixteenths rampbar rampbeat tempo beats phase`; callbacks `onNumPeersChanged`, `onTempoChanged`; **no tempo parameter, no method to set it**; ignores peers' start/stop (forum, K) | [D] + [V] help |
| MIDI In CHOP | decodes timer/beat pulses, Start/Stop/Continue, Song Position Pointer; can drive the Timeline; Mac clock timing was shaky in 2020 builds, M1 2022 "fine" per staff; 31550/Rosetta unverified | [V] help, K |
| Beat CHOP / Timecode CHOP / LTC In CHOP | tap or `bpm`; timecode generator; LTC reader (audio-in) | [D] / [V] |
| Movie File Out TOP | `videocodec` hap/prores/h264/..., `videocodectype`, alpha via RGBA pixel format, `record`, `limitlength`, realtime flag; **no DXV**; realtime at 7488x2880 drops frames | [D] + T-11 |
| Touch Out/In TOP | TCP TD<->TD, HAP Q (Alpha); same major release both ends; Mac untested | [V] X |
| Palette | `TDAbleton`, `TDBitwig`, `TDSynchro` (`synchroNDIIn.tox`) exist; **nothing for Resolume** in `Samples/Palette/` or `Samples/` | [V] `ls` |
| Community | tolch 2019 "TD + Resolume bidirectional": FFGL dummy-parameters plugin (Leskos/FFGLDummyParams) sends sliders as OSC to TD, textures by Syphon/Spout; Windows `.dll` | [V] X #14, [U] Mac |
| FFGL-host of TD | FFGLTouchEngine (djevo1, 2024): TD `.tox` inside Resolume, Spout only = Windows; **no Mac route** | [S] R |
| Our own | StageLab `JZB_*` FFGL plugins run inside Arena with no IPC (R1): single-shader looks can leave TD entirely | [V] R |

### 2. Arena side, on this Mac (read-only file facts)
- `~/Documents/Resolume Arena/Preferences/osc.xml` (written by 7.23.2 rev 51094): `<Input Enabled="0" Port="7000"/>`,
  `<Output enabled="0" sendBundles="0" targetType="2" targetPort="7001" targetAddress="127.0.0.1"/>` [V]. **One output target
  only**: whoever binds 7001 receives Arena's OSC. `server.xml`: web server `enabled="1" port="8080" address="127.0.0.1"` [V].
- `/Applications/Resolume Arena/Arena.app` reports 7.28.1 (26535) while prefs and the show say 7.23.2 (AH Q1, E bugs 9): never use
  the 7.28.1 app for show tests without asking (memory `pf26-td-live-rig`).
- Installed Arena help (English.xml, dated 6 Oct) [V]: Sources = "capture devices, NDI and Spout/Syphon servers, generative FFGL...";
  virtual outputs "can include Syphon/Spout and NDI"; "Alpha Channel Interpretation: Premultiplied is usually the way to go...
  switch to Straight"; Link toggle; BPM Tap / Resync / Pause; two SMPTE inputs; OSC Input toggle/port; OSC Output per element with
  wildcard and custom address. No "MIDI clock" text.
- Arena publishes Syphon "Arena"/"Composition" or "Screen n" (Advanced Output) [V] E 2; NDI out in Preferences.

### 3. Resolume protocols
- **REST + WebSocket** (web server, default 8080): swagger = `white-tie-live/resolume-js` copy; `PUT /composition` with a nested
  envelope is the only REST way to change tempo/crossfader; no standalone `/composition/tempocontroller/*` REST paths [S, vendor
  `swagger-probe-results.md`, static analysis, not live]. WS pushes full composition + `sources_update`/`effects_update`/
  `thumbnail_update`, parameters by id (Tortillaguy client in vendor `00-prior-art.md`) [S].
- **OSC** in 7000 / out 7001 (prefs). Live-verified by the vendor author on 7.23.2 [S]: `?` query works, `*` wildcards match one
  segment only; `/composition/layers/N/clips/M/transport/position` (clip play head, 0..1) and `/composition/layers/N/position`;
  ~325 msg/s; some UI-bound params arrive **twice** per tick; `/composition/tempocontroller/{tempo,resync}` + `tempotap`;
  tempo input is **normalised 0..1** (raw BPM breaks it). The old repo's map (`resolume7-fx-pipeline/CLAUDE.md`) uses
  `layers/{l}/opacity`; Arena docs show `layers/1/video/opacity`: another reason to re-learn.
- **Media:** Arena plays DXV (Alley/Arena convert), HAP family, ProRes, H.264 [S general knowledge]; our pipeline ingests DXV3 only.

### 4. Prior art: the `learn` approach (`resolume7-fx-pipeline/`)
`master.py learn --port 9000 --seconds 60` -> `tools/learn_osc.py`: a passive UDP sniffer (`python-osc` dispatcher default handler,
prints `address [args]`, optional save to `logs/osc_log.txt`); user turns on Arena OSC Output, wiggles faders/triggers clips, copies
real addresses into `core/osc_client.py`. Golden rules there: dry-run first (`--dry` prints exact OSC), cap sends at 30/s
(`BPMClock.min_step`), indices are 1-based in OSC, "trust `learn`, not this file". No `logs/` exists: **no learn run was ever
recorded** for 7.23.2. Our TD version reuses the idea (Patterns 4); it does not import the repo (ADR-004, no shared imports).

### 5. `resolume-723` (mackatwentytsuru v0.5.4, 37 tools exposed at `stable`; manifest holds 39: `resolume_cache_refresh` alpha and
`resolume_tap_tempo` beta are hidden) [V `src/tools/tool-manifest.json`, AUDIT]
Names: `resolume_add_effect_to_layer`, `_cache_status`, `_clear_clip`*, `_clear_layer`*, `_get_beat_snap`, `_get_clip_position`,
`_get_clip_thumbnail`, `_get_composition`, `_get_crossfader`, `_get_tempo`, `_list_layer_blend_modes`, `_list_layer_effects`,
`_list_layer_transition_blend_modes`, `_list_video_effects`, `_osc_query`, `_osc_send`, `_osc_status`, `_osc_subscribe`,
`_remove_effect_from_layer`*, `_resync_tempo`, `_select_clip`, `_select_deck`, `_set_beat_snap`, `_set_bpm`, `_set_clip_play_direction`,
`_set_clip_play_mode`, `_set_clip_position`, `_set_crossfader`, `_set_effect_parameter`, `_set_layer_blend_mode`, `_set_layer_bypass`,
`_set_layer_opacity`, `_set_layer_transition_blend_mode`, `_set_layer_transition_duration`, `_trigger_clip`, `_trigger_column`,
`_wipe_composition`* (* = destructive, `confirm:true`). Defaults: REST 127.0.0.1:8080, OSC in 7000, OSC out 7001.

What they can do **once TD's output is a Syphon/NDI clip** (the clip is placed by the user):
| Job | Tools |
|---|---|
| Find the TD clip, slot, names | `get_composition` (layers/clips/names; Syphon clip name = [U]), `select_deck`, `select_clip` |
| Fire / stop the TD look | `trigger_clip`, `trigger_column` (a live source has no play head: `get_clip_position`, `set_clip_position`, `set_clip_play_*` are [U]/n/a) |
| Mix it in the show | `set_layer_opacity`, `set_layer_bypass` (the Arena-side **kill** of layer 6, E 6), `set_layer_blend_mode` (Add), `list_layer_blend_modes`, `set_layer_transition_*`, `set_crossfader`/`get_crossfader` |
| Grade it in Arena | `list_video_effects`, `add_effect_to_layer`, `set_effect_parameter` (read back after each set; the v0.5.1 cache-hit no-op was fixed in 0.5.2), `list_layer_effects`, `remove_effect_from_layer`* |
| Look at it | `get_clip_thumbnail` (inline image; probably the stored thumbnail, not live: [U]) next to `td_screenshot` |
| Tempo | `get_tempo`, `set_bpm` (20..500), `resync_tempo`, `get_beat_snap`/`set_beat_snap` |
| OSC | `osc_send` (to 7000: any path), `osc_query` (`?`, replies arrive on **7001**), `osc_subscribe` (binds **7001** for the call), `osc_status` |
They cannot: add a Syphon/NDI source, load media, change Advanced Output/slices, read audio levels (no FFT over any API, vendor CLAUDE.md).
`resolume-arena` (7.26+): `clip open` with a file path, `monitor` snapshot/filmstrip, `diagnose`, `parameter`, `transport` (AH): it can
load a DXV into a clip on 7.26+; on 7.23 that is by hand.

## Patterns
Each: signal flow, latency/reliability, failure modes. Wire names are stable and short.

**1. Live video TD -> Arena (Syphon, same Mac).** `look COMP/out -> Null TOP out_<name> -> (Fit/Resolution TOP to the target size)
-> (Level TOP premult) -> Syphon Spout Out TOP`. Pars: `sendername` e.g. `TD_<project>_<look>` (stable; Arena stores the source by name),
`active` last. 8-bit RGBA only, so keep 16-bit inside feedback loops and dither (`rampTOP.dither`) before the sender if gradients
band (TOP.md). Set `project.cookRate` to Arena's composition fps (30; Arena 7.23.0 smooths playback when the comp rate is fixed, R).
Cost: 86.3 MB/frame at 7488x2880 (2.6 GB/s at 30 fps, E 2), unmeasured end to end. Latency: expect 1-2 frames [U]. Syphon has no
queue: duplicated/skipped frames when clocks free-run (staff comment was about Spout, [S]/[U] for Syphon). Failure modes:
sender vanishes (TD quit/crash/`active` off) -> Arena behaviour untested (E 6: black, frozen last frame, or red OFFLINE until
restart, forum snippets, older builds); renaming the sender orphans the clip; Rosetta-server/native-client pairing unreported.
**Design that survives all of them:** Arena layer above BASE with Add blend + an Arena-side kill that works with TD dead.

**2. Live video TD -> Arena (NDI).** Same chain, `NDI Out TOP`: `name` = `TD_<look>`, `fps` 30, `lowperformancebehavior = skipframes`
(never stall the main thread: T-43), `outputpixelformat fixed8`, `includealpha` only if needed (+25 % bandwidth, E 3),
`failovername` for a backup Mac. Arena shows it as `HOST (name)`; Wi-Fi off, Arena allowed in macOS Local Network privacy, same
IP range for two machines [V E/Arena doc]. Info CHOP `skipped_frames` + `last_send_time` -> log. NDI is the 2-machine path;
on one Mac it buys only 16-bit and alpha options. Failure modes: Arena 7.21.3 Apple Silicon "NDI OFFLINE until restart" snippet (R);
red Offline mark at 0x0 when ranges differ.

**3. Alpha/premultiplied handling (TD -> Arena).** TD generators (Render, Text, Circle, Ramp, Constant, GLSL, Movie File In) default
`premultrgbbyalpha` on [D], and `overTOP` assumes premultiplied, so a normal TD composite is already premultiplied. Arena clip
Alpha Type defaults Premultiplied. So **default: send premultiplied, leave Arena's Alpha Type on its default.** If halos appear,
either flip that clip to Straight or un-premultiply in TD; do not guess. There is no Premult/Unpremult TOP in the dump; premultiply
= Level/GLSL/Constant `premultrgbbyalpha`, un-premultiply = a 3-line GLSL TOP (`rgb/max(a,1e-4)`). Numeric self-check in TD
(no Arena): on the final Null, `numpyArray()` (force-cook first, T-13), assert `max(r,g,b) <= a + 1/255` for premultiplied (as in
`hyperframes` H-34/35 checks). Arena check: a horizontal alpha ramp 0..1 over white, Arena layer over a mid-grey with Alpha and
Add blends; read Arena's own "Composition" Syphon back into TD and compare to `rgb + bg*(1-a)` numerically (Test plan T5).
`td_screenshot` flattens alpha over white (T-12): never use it to judge alpha. NDI `includealpha` carries straight or
premultiplied? [U] — test with the same ramp.

**4. OSC address verification per build (learn, TD edition).**
Wiring: user enables Arena Preferences > OSC Output (target 127.0.0.1:7001, already in prefs) -> TD `OSC In DAT` `arena_learn`
(port 7001, Clamp off or `Max Lines` large, address scope `*`, Callbacks DAT appends to a Table DAT `learned`: address, args,
count, first/last seen) -> `td_exec` exports `output/arena_osc_<arena build>.json`. Procedure = the old repo's: wiggle each control,
trigger clips, change tempo, then diff against the pipeline map (`layers/{l}/opacity` vs `layers/{l}/video/opacity`,
`dispatchclipfire`, `connect`, `bypass`, `master`). Ask-by-`?` for single addresses (`osc_query` or an OSC Out DAT `?` while
`arena_learn` listens). Record the build string (`/api/v1/product` or the prefs `versionInfo`) in the file name; **re-learn on any
Arena change**. Port rule: Arena has **one** OSC Out target. If TD owns 7001, `osc_query`/`osc_subscribe` and the `RESOLUME_CACHE`
store (binds 7001) hit EADDRINUSE and degrade to empty results (vendor CLAUDE.md); `osc_send` still works (it only sends to 7000).
Either give 7001 to TD for the rig and use REST for reads, or let the MCP own it during learn sessions only. A broadcast/multicast
target so both can listen is [U].
TD -> Arena commands: `OSC Out DAT.sendOSC('/composition/layers/6/video/opacity', v)` to 127.0.0.1:7000; floats are 0..1, indices
1-based; cap at 30 msgs/s (pipeline rule 2); never address a layer the learn file has not seen.

**5. Arena -> TD video, and the feedback trap.** Arena Syphon "Composition"/"Screen n" or NDI out -> `Syphon Spout In TOP`/`NDI In
TOP` (`sendername` / `name`). Use a **small virtual Screen** (e.g. 1080x1920 or the IMAG feed) for TD; the 7488x2880
composition in TD costs 86 MB/frame. If layer 6 holds TD's own sender, the composition output contains TD's image: a
feedback loop with >= 2 frames of delay per trip. Route TD's input from a screen/layer that excludes layer 6 (Advanced Output
slice routing, E 4.3) [U]. Existing evidence: the PF26 viewer bridge read Arena's NDI at 27-28 fps (SYSTEM.md, E 3).

**6. State out of Arena (REST/WS).** Web Client DAT polls `GET http://127.0.0.1:8080/api/v1/composition` at 1 Hz (JSON ->
`Convert`/`json` in a callback) for tempo, selected column, layer opacity/bypass, clip names; or WebSocket DAT to
`ws://127.0.0.1:8080/api/v1` for push [S]. This replaces OSC when 7001 is taken, and gives TD a post-relaunch resync (R2: TD reads the
current layer-6 clip and lands in the right look). Rate limit REST to a few req/s: Arena's HTTP server loses throughput beyond
~8 in flight (vendor config comment) [S]. 7.23 vs 7.26+: see Patterns 9.

**7. BPM / clock sync, both ways.**
| Route | Direction | Notes | Tag |
|---|---|---|---|
| Ableton Link | Arena <-> TD <-> Ableton | Arena Link toggle + `abletonlinkCHOP enable=1`; while Link is on Arena's Resync/Pause are off; tempo changes by any peer reach all; TD cannot set tempo, so the tempo owner is Arena or Ableton; start/stop is ignored by TD's CHOP | [V] help, K |
| Arena OSC tempo | Arena -> TD | OSC Out of `/composition/tempocontroller/tempo` (value normalised: `bpm = min + v*(max-min)`; min/max from `get_tempo` = 20/500 live on 7.23.2) | [S] |
| REST tempo | both | `resolume_get_tempo`/`set_bpm` (PUT `/composition` `tempocontroller.tempo.value`); TD can poll with Web Client DAT or PUT the same body | [S] |
| OSC to set tempo | TD -> Arena | send **normalised** value `(bpm-20)/480`, or tap/`resync` triggers; verify by `?` readback | [S]/[U] |
| MIDI clock | ext -> TD | MIDI In CHOP timer/beat/start/stop; **Arena has no documented MIDI-clock input**, so TD -> Arena by MIDI clock is not available; relay via OSC/REST | [V]/[U] |
| SMPTE/LTC | ext -> both | Arena has two SMPTE audio inputs; TD `ltcinCHOP`; for backing-track acts (K11) | [V] |
| Tap in TD | local | `beatCHOP` + tap for TD only; Arena stays as is | [D] |
Failure modes: Link over Wi-Fi/firewall, Link "doesn't work with all sound drivers" [V help]; Rosetta TD + Link untested.
Phase: Link aligns to the bar quantum, not to Arena's clip start; beat-snapped triggers (`set_beat_snap`) use Arena's own clock.

**8. Clip hand-off (TD render -> Arena).** TD records offline (`project.realTime=False`; realtime drops frames at 7488x2880, T-11):
`Movie File Out TOP` ProRes 422 HQ master (4444 + RGBA when alpha) -> `ffprobe -count_frames` equals the loop length (69 vs 71 seen)
-> **DXV3 via Alley CLI** `"/Applications/Resolume Alley/Alley.app/Contents/MacOS/Alley" --convertTest --path <copy> --preset
"DXV High Quality With Alpha"` (H-36: scratch copy, wait for frame count, kill Alley) -> into the pipeline folders
(`production/assets_where.py`, file names start with the viewer ID: PF26 only, C_pf26_fit 3). **Hap/Hap Q direct**
(`videocodec=hap`, `videocodectype` Hap Q; TD always 12 chunks; Hap Q is ~1 byte/pixel = 21.6 MB/frame at 7488x2880) is the faster
path but the pipeline standard is DXV3, and Arena playback of either at wall size is untested. Alpha clips: premultiplied masters,
assert colour <= alpha, simulate Arena's blend, say "not checked in Arena" until it is. Arena import: by hand on 7.23
(`resolume-723` has no load tool); `resolume-arena` `clip open` on 7.26+ [AH]. Never write into Arena's prefs/compositions.

**9. REST on 7.23 vs 7.26+.** 7.23.2: web server (prefs `server.xml`), swagger as vendored, `GET /api/v1/product` exists on later 7.x,
404 on older (vendor CLAUDE.md) [S]; tempo/crossfader by wide `PUT /composition`; per-layer `POST .../clearclips`; thumbnails at
`.../thumbnail`; the vendor claims a live test on 7.23.2 (`live-test-v0.5.1.md`: 33 of 39 tools exercised) [S]. 7.26+: Resolume's
bundled MCP requires it [V AH manifest]; what it adds on the REST side (clip open by path, parameter animation sources,
monitor/diagnose) is known only from the binary's type names [U]. Diff plan: read-only `GET /composition` keys and `/api/docs`
on both builds when the user allows the 7.28.1 app (Test plan T11). Our rule: gate 7.26+ features by `GET /product` version, keep
them in FUTURE.md, never drop them because 7.23 lacks them.

**10. Show-safe behaviour.** TD kill = `active=0` on the sender + output alpha 0 (E 5), Arena kill = layer-6 bypass/opacity on a
physical button (`set_layer_bypass` for sessions), both from one MIDI press (R). `docs/WATCHDOG.md`'s heartbeat can also send one
OSC packet to Arena (opacity 0) before it kills a hung TD (R proposal). Crossfade/scene logic stays in TD (E 5.5, H).

## Proposed upgrades (jazib-td)
Rules: one structural change per call, `td_layout flow` after, viewers on, `build_gate()` (`td/handlers.py`) around anything
build-specific, FUTURE.md rows, `active=0` default for any sender, never write Arena files, sends are dry-run by default.
| Tool | Args | Side (`src/server.js` registers; `td/handlers.py` builds) | Builds / returns | Pairs with |
|---|---|---|---|---|
| **`td_publish`** | `source` (TOP path or COMP with an out TOP), `kind` `syphon\|ndi\|both`, `name`, `size` `[w,h]\|"input"`, `fps` (default `project.cookRate`), `alpha` `premultiplied\|straight\|none`, `parent`, `active` (false) | `plain('td_publish','publish')`; `cmd_publish` + pure `plan_publish()` (names, res, pars: unit-testable) | Null `out_<name>` -> optional Fit -> optional alpha Level/GLSL -> `syphonspoutoutTOP` and/or `ndioutTOP` (skipframes, fixed8, `includealpha` from `alpha`) + Info CHOP; creates in one `undo_block`; **returns** `{ops, sender:{syphon:name, ndi:"HOST (name)"}, res, fmt, cookRate, alphaNote, arena:["Sources > Syphon > <app> - <name>" , "drag onto a clip in a scratch column", "layer blend Add", "clip Alpha Type = Premultiplied (default)"], hostname}` | `resolume_get_composition` (find clip), `resolume_set_layer_blend_mode` Add, `resolume_trigger_clip` |
| `td_publish` `enable`/`disable` | `name`, `active` | same cmd, `action` arg | flips `active` (Syphon/NDI operation = user gate) | `resolume_set_layer_bypass` for the Arena kill |
| **`td_publish_status`** | none | read-only `cmd_publish_status` | every Syphon/NDI Out/In in the project: name, `active`, res, fmt, cook ms, NDI `skipped_frames`/`last_send_time`; NDI DAT source list; warns on duplicate sender names, non-8-bit Syphon, name != stable pattern | `resolume_get_composition` (compare names), `td_perf` |
| **`td_arena_link`** | `action` `learn_start\|learn_stop\|learn_export\|dry_send\|send\|poll_start\|clock_start`, `host`, `in_port` 7000, `out_port` 7001, `address`, `args`, `rest_port` 8080 | `cmd_arena_link` | builds `OSC In DAT arena_learn` + Table DAT `learned` + Callbacks; exports `output/arena_osc_<build>.json`; `dry_send` returns the exact OSC packet; `send` refuses addresses not in the learned file unless `force`; `poll_start` = Web Client DAT 1 Hz to a Table; `clock_start` = Pattern 7 chain (below) | `resolume_osc_status` (is 7001 free?), `resolume_osc_query`, `resolume_get_tempo` |
| **`td_clock`** (recipe first, typed later) | `source` `link\|arena_osc\|arena_rest\|midi\|tap` | `td_exec` recipe, then `cmd_clock` | Null CHOP `clock` with `bpm`, `beat`, `bar`, `phase` fed from a Switch CHOP over: Link CHOP (callbacks log `onTempoChanged`), Web Client poll, OSC In (decode normalised tempo with min/max), MIDI In CHOP, Beat CHOP | `resolume_set_bpm`/`get_tempo`; Ableton MCP if Link master |
| **`td_clip_bake`** | `source`, `frames`, `codec` `prores\|prores4444\|hap_q`, `file`, `alpha` | `cmd_clip_bake` (offline: realtime off, frame-count check with `ffprobe` via exec) | Movie File Out TOP, records exactly N frames, restores `project.realTime`, returns `{file, frames_expected, frames_found, bytes}`; premultiplied assertion on the Null first; a printed (not run) Alley DXV3 command | `production/assets_where.py` (PF26), Arena import by hand / `resolume-arena clip open` (7.26+) |
| `td_arena_check` (doc, not a tool) | - | `docs/USING_TD.md` addition | the 5-step "TD source visible in Arena" checklist (Test plan T4-T5) | `get_clip_thumbnail`, `td_screenshot` |
Build gating: Syphon Out is macOS only (`sys.platform`), NDI par names read from `o.par` (skip a par the build lacks, note it);
`td_publish` returns `available:false` + note on a build where `syphonspoutoutTOP`/`ndioutTOP` are not creatable.
`td_arena_link send` is the only tool that talks to Arena and only after the user's per-call go-ahead; `learn_*` and `poll_*` open
local ports and are also gated (Syphon/OSC/REST operations, CLAUDE.md).

## Test plan
**Offline (no TD, no app) — do first.** (a) `test/test_handlers.py`: `plan_publish()` cases (name sanitising, res clamp, NDI name
`HOST (name)`, par dicts for each `kind`/`alpha`, duplicate names), OSC packet encoder for `dry_send` (normalised tempo math,
1-based index check), learned-file diff against the pipeline map. (b) `test/offline.test.mjs`: zod schemas, tool registered, help text.
(c) Docs: PROTOCOL.md row per command. Expected: `npm test` green, no network.
**Live, in order** (TD = safe; GA = needs the user's go-ahead each time; APP = Arena open):
| # | Step | Kind | Expected |
|---|---|---|---|
| T1 | `td_publish` in a scratch COMP with `active=false`; `td_errors`, `td_layout check`, `td_screenshot` | TD-only | 4-5 ops, left-to-right, no errors, pars as planned, no server visible to other apps |
| T2 | `td_publish_status` lists the new ops and flags nothing | TD-only | one row per sender, `active` false |
| T3 | `active=true` Syphon (no Arena) and read it with a Syphon client (PF26 viewer bridge or `Syphon Spout In TOP` in the same TD) at 1920x1080, then 3744x1440, 7488x2880 | GA (Syphon op) | publishes; orientation known (use a pattern with a top, L-54); fps and cost recorded |
| T4 | Arena scratch composition (not the show file): source appears under Sources; user drags it into a clip; `resolume_get_composition`, `resolume_get_clip_thumbnail`; `resolume_set_layer_blend_mode` Add | APP+GA | listed as `<app> - <name>`; clip name recorded; orientation/scale/fps judder at 30 vs 60 noted |
| T5 | Alpha ramp over white -> Arena (Alpha and Add) -> Arena "Composition" Syphon back into TD -> numeric compare with `rgb + bg*(1-a)` | APP+GA | premultiplied path matches; straight path haloes; decision recorded (also for NDI `includealpha`) |
| T6 | OSC learn: user enables Arena OSC Output; `td_arena_link learn_start`; wiggle layer 1 opacity, trigger clip, change BPM; `learn_export` | APP+GA | `arena_osc_7.23.2.51094.json`; diff vs old map (`opacity` vs `video/opacity`) |
| T7 | `dry_send` then one real send to a scratch layer's opacity; `resolume_get_composition` / `?` readback | APP+GA | value changes, readback equal; no other layer touched |
| T8 | Tempo: `resolume_set_bpm` 120 -> TD sees it by REST poll and OSC; Link on in both, compare tempo and phase | APP+GA | tempo equal; normalised OSC math confirmed; Link phase offset measured; MIDI clock noted as unsupported |
| T9 | Source-drop: `active` off, quit TD, `kill -9`, SIGSTOP, heavy hitch; then recover by name | APP+GA | the four outcomes of E 6 recorded for Syphon and NDI; kill via `set_layer_bypass` works with TD dead |
| T10 | `td_clip_bake` a 2 s loop (ProRes 4444 with alpha, Hap Q) -> Alley DXV3 -> drop into Arena; premultiplied check | APP+GA | frame counts match; Arena blend matches the simulation |
| T11 | (only if allowed) 7.28.1 app + `resolume-arena`: `GET /product`, REST key diff vs 7.23.2 | APP+GA, not the show host | the 7.23 vs 7.26+ REST delta written to this file |
After each step: `td_errors`, `td_layout check`, delete scratch ops, LEARNINGS T-nn for every bug.

## Gates
- Every Arena call, REST, OSC and Syphon/NDI start needs the user's go-ahead each time (CLAUDE.md, mcp-vendor README). Do not put
  `resolume-*` tools or `td_arena_link send` in an allow rule. "Read-only" Arena calls are still Arena traffic.
- Arena 7.23.2 is final and the show host; the 7.28.1 app is not used for show tests. Never `AdvancedOutput.xml`/`slices.xml`/prefs writes.
- `resolume_osc_send` can send any path; `wipe_composition`, `clear_*`, `remove_effect` need `confirm:true` and an explicit user ask.
- TD: viewers on, arrange, build-gate, FUTURE.md rows; no Rosetta-unsafe self-scheduling `run()` chains (E bug 1).
- Alpha claims stay "not checked in Arena" until T5/T10 pass. No performance number without hardware and method.

## Sources
Files read: `docs/research/{E_live_rig,R_show_safe_interactive,X_tutorials_workflow_output,K_audio_reactive,AH_relevant_mcps,C_pf26_fit}.md`,
`docs/research/ops/{TOP,CHOP,DAT,PLATFORM}.md` + `ops_*_2025.31550.json`, `LEARNINGS.md` (T-11, T-12, T-13, T-43), `AUDIT.md`, `docs/FUTURE.md`,
`docs/WATCHDOG.md`; TD offline help in `TouchDesigner 2.app/.../Samples/Learn/OfflineHelp/https.docs.derivative.ca/`
(`Syphon_Spout_Out_TOP`, `NDI_Out_TOP`, `Ableton_Link_CHOP`, `AbletonlinkCHOP_Class`, `MIDI_In_CHOP`); `Samples/Palette/` listing;
Arena: `~/Documents/Resolume Arena/Preferences/{osc,server}.xml` (read-only), `/Applications/Resolume Arena/docs/help/English.xml`;
`mcp-vendor/resolume-mcp-server/{CLAUDE.md,README.md,CHANGELOG.md,src/tools/tool-manifest.json,src/config.ts,src/resolume/tempo.ts,
src/tools/osc/*.ts,docs/v0.5/{swagger-probe-results,live-test-v0.5.1,osc-duplicate-investigation,00-prior-art}.md}`;
`resolume7-fx-pipeline/{CLAUDE.md,STATUS.md,tools/learn_osc.py}`; `hyperframes/LEARNINGS.md` H-34..H-36; memory `overlay-alpha-premultiplied`,
`pf26-td-live-rig`. Web (via E/R/X, not re-fetched): Resolume support pages Syphon & Spout, NDI, OSC, Link, SMPTE, Input Selection;
tolch tutorial `derivative.ca/community-post/tutorial/.../61081`; Derivative forum Spout/Syphon queue thread.

## Open questions
1. **Which Arena build is the show host in practice** (prefs and docs say 7.23.2 rev 51094; the app bundle says 7.28.1)? Decides T11 and whether
   `resolume-arena` is usable at all.
2. May OSC Output (7001) belong to TD for the rig, accepting that `osc_query`/`osc_subscribe` go quiet, or should the MCP keep it and TD
   use REST polling only?
3. NDI alpha: straight or premultiplied on the wire, and does Arena's Alpha Type apply to Syphon/NDI clips? (T5 answers.)
4. Syphon server naming in Arena's list (`TouchDesigner - name`?) and whether a renamed sender recovers; whether Arena's sender
   scan refreshes without a restart.
5. Does Arena 7.23.2 follow external MIDI clock at all (not in the installed help), or only Link/tap/SMPTE?
6. Is the OSC tempo scale exactly `(bpm-20)/480` on this build (min 20, max 500 from `get_tempo`)? Confirm with `?` readback.
7. Portrait 1080x1920 TD builds vs the 7488x2880 wall: should `td_publish` offer an "atlas" compose step (place the look into a
   named region), or is that a show-specific job for the PF26 rig?
8. Is a broadcast/multicast Arena OSC target acceptable so TD and the MCP can both listen on 7001?
9. Hap Q direct vs DXV3 for TD-made loops: does the user want Hap Q allowed in the PF26 pipeline, or DXV3 only?
10. Do you want `td_arena_link` to ship with the REST poll only (no OSC) first, since REST reads need no extra port?
