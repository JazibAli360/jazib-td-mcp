# BD: twozero "TIMELINE" rudiment, clean-room build spec for `LK_timeline` (research, 26 Oct 2026)

Research only: nothing loaded into TD, nothing run, nothing installed, no sign-in. Clean-room: we study what it does, we copy no code.
`research_src/rudiments_timeline/` was created but stays **empty**: no .tox was downloadable without an account (section 1.2).
Siblings the user also listed (zerror, screen-reprojection, db-meter, vankrav face-tracking, previz-stage) are separate BE..BI notes; section 4 gives the face-tracking and dB-meter pointers this brief asked for.

## 1. What the original is, and how much we could learn

### 1.1 Sources actually obtained (all fetched 26 Oct 2026)
| Source | Got |
|---|---|
| https://twozero.ai/rudiments/twozero/timeline (and `app.twozero.ai/...`) | HTTP 200, but a JS single-page app: the HTML is a ~10 KB shell. WebFetch saw only the word "TIMELINE". Server-side meta only (below). |
| `og:description` / `description` meta | "A production timeline for TouchDesigner - clips, keyframes, proxies, recording and AI audio tools, fully open and agent-ready." og:title `TIMELINE`, og:site_name TWOZERO, cover image `https://app.twozero.ai/rudiments/twozero/timeline/cover.jpg` (not fetched). |
| https://twozero.ai/rudiments | same shell, no listing in HTML. |
| https://twozero.ai/docs/rudiments (public) | meta only: "Production-grade building blocks for TouchDesigner, built by 404.zero and setupdesign for real shows. Browse them at twozero.ai/rudiments." |
| https://twozero.ai/sitemap.xml | lists /docs/* (requirements, installation, toolset, mcp, zops, library, hub, palette, vst, rudiments, changelog...), /playbook/*, pricing; **no rudiment URLs, no GitHub/video links**. |
| https://twozero.ai/llms.txt | API guide for their own service (auth headers x-user-id / x-access-key; public: /api/health, /api/repos/list-repos, /api/feed). The public repo list (4 repos: knowledge_samples, mcp_knowledge, ...) has nothing named timeline. Not pursued further: protected endpoints need an account and we do not sign in. |
| Download | No public .tox link anywhere. Rudiments appear to be delivered inside the twozero app/hub (an account product with Pro tier: /pricing, /docs/pro, /docs/hub). Not bypassed. **Licence unknown** (not on the page; irrelevant for research). |

**Consequence: everything below under "original" is limited to the one sentence above plus what a production timeline in TD normally means. Features marked (inferred) are our reading, not observed.** No parameter names, UI layout or file format of the original are known. We never needed them: the spec in section 2 is designed from the user-visible promise.

### 1.2 What the original does (stated, then inferred)
Stated (from the meta line): a timeline for TouchDesigner with
1. **clips** (media blocks placed on tracks),
2. **keyframes** (animated parameters/channels),
3. **proxies** (low-res stand-ins for heavy media while editing),
4. **recording** (capture the output/params to file),
5. **AI audio tools** (their cloud/AI side: e.g. stem split, beat/transcribe; (inferred), account/credit-gated, **out of scope for us**),
6. "**fully open and agent-ready**": the network is plain TD ops with documented structure that an MCP/agent can drive (matches twozero's own MCP product: /docs/mcp).
Inferred typical UI: transport (play/pause/loop/scrub/in-out), a ruler with the playhead, tracks with draggable clips, a curve/keyframe lane, a window of its own. Not verified.

Prior art we already hold: Palette `animation` COMP (curve editor), `keyframeCHOP`, TD's own timeline (`timelineCHOP`), AE import as Animation COMP idea (docs/FUTURE.md, `AK_td_aftereffects.md`), VJ layer system `AU_vj_5layer_system.md`, `E_live_rig.md`, show panel `docs/SHOW_PANEL.md`. Nothing in our research folder builds a clip timeline (grep of README: no row).

## 2. CLEAN-ROOM BUILD SPEC: `LK_timeline`

Goal: one self-contained COMP that plays a **cue list of clips and keyframed parameter lanes against its own clock**, with proxies, recording, and a controls window. Design for our use: PF26 loops/visualizers preview, MCP-drivable (`td_set_pars`, `td_dat_text`), deterministic, testable offline.
Scope cut (build only what was asked / "similar functionality"): clips, keyframes, proxies, recording. AI audio tools = **not built** (cloud, paid); instead an audio-track lane fed by an Audio File In CHOP (local, free).

### 2.1 Custom parameter pages (names: one capital, then lowercase/digits)
| Page | Pars |
|---|---|
| `Transport` | `Play` (toggle), `Loop` (toggle), `Rate` (float, -4..4, default 1), `Fps` (float 30), `Length` (float s, 60), `Inpoint` / `Outpoint` (float s), `Seek` (float s, the playhead; written by the clock), `Gotostart` / `Gotoend` / `Stepfwd` / `Stepback` (pulses), `Tcmode` (menu seconds / frames / smpte) |
| `Clips` | `Cliptable` (DAT ref to the clip table), `Sourcemode` (menu full / proxy / auto), `Proxyres` (menu 25% / 50% / 1/4 res), `Premult` (toggle, keeps alpha premultiplied, see Overlay alpha memory), `Fade` (float s, default crossfade), `Blendmode` (menu over / add / screen) |
| `Keys` | `Keytable` (DAT ref), `Interp` (menu hold / linear / ease / bezier-ish smoothstep), `Lanes` (read-only count) |
| `Record` | `Rec` (toggle), `Recfile` (str), `Reccodec` (menu prodres422 / hapq / h264), `Recfps`, `Recwhat` (menu output TOP / lane CHOP csv), `Recstart` / `Recstop` (pulses), `Recframes` (read-only) |
| `Output` | `Resx`, `Resy` (full res), `Bgcolor`, `Showtc` (burn timecode over output, off by default, never in the Out) |
| `Panel` | `Opencontrols` (pulse), `Pagetabs` kept off in the panel |
Built with `td_custom_pars`; the clip/key tables are internal Table DATs, the Cliptable/Keytable pars default to them (user can point at another DAT). Resolume rule: nothing here writes Arena.

### 2.2 In / Out
- `In1` (In TOP): optional **live layer** composited as the bottom track when `Sourcemode` allows (so the timeline can sit over TD live content).
- `In2` (In CHOP): optional external time (e.g. beat/timecode); when its first channel `time` is connected and `Extclock` (Transport toggle, add) on, the clock follows it.
- `Out1` (Out TOP): **the composite only**. `Out2` (Out CHOP): lane values (one channel per keyed lane, plus `tl_time`, `tl_play`). Nothing else (no controls) goes into the Outs.

### 2.3 Internal network, stages (for `td_layout mode:"stages"`, L->R inside a stage)
1. **Clock** (CHOPs + a small `clock` Script CHOP or Speed-driven Lag): `speedCHOP` driven by `Play*Rate`, resets on `Gotostart`, wrapped by `Loop` between `Inpoint` and `Outpoint` (a `mathCHOP` + `limitCHOP type loop`/`clamp`), output `t` seconds + `frame`. Write `Seek` back from a CHOP Execute DAT only when scrubbing is not user-held (avoid fighting: scrub sets `Seek`, clock reads `Seek` when `Play` off).
2. **Cue tables** (`tableDAT` `clips`: `id, track, start, dur, src, in, speed, fade, proxy, enabled`; `tableDAT` `keys`: `lane, par, t, value, interp`). Edited by the panel, by `td_dat_text`, or imported (csv/json).
3. **Active clips** (`scriptDAT`/Python, pure logic): from `t` pick the clips whose `[start, start+dur)` contain it, compute `localtime = in + (t-start)*speed`, crossfade weights from `fade`, ordered by track. Output a small `active` Table DAT (max 8 rows) that the next stage reads by expression.
4. **Players**: a fixed bank of **4 Movie File In TOPs** (`moviefileinTOP`, `Playmode` = specify index, `Index` = frame from localtime*fps, so the timeline never relies on each movie's own clock and scrubbing is exact), each fed `File` = `src` or its **proxy path** (`Sourcemode`). Spare players are `play off`/blank. Cook bypass for empty ones.
5. **Proxy maker** (Python, offline-first): for each clip a proxy file `<name>_proxy.mp4` (or `.mov` Hap) created by an `ffmpeg` subprocess run from the **MCP/offline side**, not inside TD (TD's cook must not block; ffmpeg is already in our toolchain). The panel only shows "proxy ready / missing"; `Sourcemode auto` = proxy while scrubbing, full when playing. (Clips are our own `.mov` ProRes/Hap masters, so this matters.)
6. **Composite**: `compositeTOP` chain / one `glslTOP` in **compute mode** weighing 4 layers + live `In1` (T-46: do not chain multi-pass fragment GLSL; a single compute-mode shader with 5 sampler inputs, `uWeight[5]` as uniforms, premultiplied accumulate). Optional `Bgcolor` under.
7. **Keyframe lanes**: `keyframeCHOP` per lane is heavy to build from a table; prefer a Python `scriptCHOP` that reads `keys`, evaluates every lane at `t` with the chosen `interp` (sketch below) and returns one channel per lane. A `lane router` CHOP Execute / Parameter binding sets target pars (`par` = `op('/proj/x').par.Foo`) only for lanes with a valid target, wrapped in try/except, so a bad lane never breaks the clock. Output also goes to `Out2`.
8. **Record**: `moviefileoutTOP` fed from the composite, `Rec` drives `record`, file/codec from `Record` page; a `recorder` CHOP Execute resets `Recframes`. Frame-accurate offline render (play from 0 at fixed step) = `Recwhat` plus `Rate=0` stepping by script, not real-time capture, for deterministic output. Second path: lanes to csv.
9. **Preview + text**: `textTOP` timecode overlay (`Showtc`) composited into a *separate* `preview` TOP, not the Out. 
10. **Controls**: `controls` panel (autoUI of the COMP, `Pagescope` = Transport, Clips, Keys, Record, `Pagetabs` off, `align verttb`, widget clones cut), plus a custom **ruler/lane view**: a `containerCOMP` `ruler` with the playhead (a Rectangle, x = t/Length), clip bars made by a `repliCOMP`/`containerCOMP` per row of `clips` (position from start/dur), mouse-click scrub through panel values. `controls_window` (`windowCOMP`, `Opencontrols` pulse, 1280x720, not full screen).

Role colours and titled stage boxes as in USING_TD 'Readable networks'. Default stage arrangement `mixed`, the Controls stage on top of column 0.

### 2.4 Code sketches (pure Python, unit-testable offline)
```python
# lk_timeline_logic.py (no td imports)
def wrap(t, a, b, loop):                      # playhead into [a,b]
    if b <= a: return a
    if loop: return a + (t - a) % (b - a)
    return min(max(t, a), b)

def active_clips(clips, t):                   # clips: list of dicts
    out = []
    for c in clips:
        if c['enabled'] and c['start'] <= t < c['start'] + c['dur']:
            local = c['in'] + (t - c['start']) * c['speed']
            fi = min(1.0, (t - c['start']) / c['fade']) if c['fade'] > 0 else 1.0
            fo = min(1.0, (c['start'] + c['dur'] - t) / c['fade']) if c['fade'] > 0 else 1.0
            out.append((c['track'], c['src'], local, min(fi, fo)))
    return sorted(out)[:4]

def lane_value(keys, t, interp):              # keys sorted by t: [(t, v)]
    if not keys: return 0.0
    if t <= keys[0][0]: return keys[0][1]
    if t >= keys[-1][0]: return keys[-1][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t < t1:
            u = (t - t0) / (t1 - t0)
            if interp == 'hold': return v0
            if interp == 'ease': u = u * u * (3 - 2 * u)
            return v0 + (v1 - v0) * u
```
GLSL compute sketch: `layout(local_size_x=8, local_size_y=8) in; uniform float uW[5]; vec4 acc = vec4(0); for i<5: acc += texelFetch(sTD2DInputs[i], ivec2(gl_GlobalInvocationID.xy), 0) * uW[i]; imageStore(mTDComputeOutputs[0], ..., acc);` (premultiplied add, weights sum <= 1 on a crossfade, an `over` mode composites in order).

### 2.5 Offline tests (pytest, no TD)
`wrap` (loop/clamp edges, inpoint==outpoint), `active_clips` (boundary start/end, fade 0, overlap > 4 clips truncated by track order, speed 0.5/2, negative rate path), `lane_value` (before/after, hold/linear/ease, duplicate times, unsorted input sorted), clip/key csv and json round-trip, timecode formatting (seconds/frames/smpte at 30, 29.97 drop frame is "gated"), proxy path naming + missing detection, record frame count = ceil((out-in)*fps). Put under `jazib-td-mcp/tests/` next to existing tests (name `test_lk_timeline.py`).

### 2.6 Verify live (after build, user's go-ahead for the live step)
- Build with a 3-clip table from existing 1-5 s masters in the repo (a pilot, one clip first), `td_inspect` on the Out CHOP: `tl_time` must advance ~1.0 s per second at `Rate 1` (mean delta per frame = 1/60 within 2%), stop at Outpoint with `Loop` off, wrap with it on.
- Seek to the exact middle of clip A and compare the Out1 frame to the same frame of the source (`td_inspect` per-RGBA means within 1/255, premultiplied).
- Crossfade midpoint: Out mean = average of both clip means (+-2%).
- Keyframe lane: set lane `Opacity 0->1` over 2 s; `td_inspect` Out2 channel min 0, max 1, monotonic.
- Proxy toggle: Out1 resolution stays `Resx x Resy`; cook time (`td_perf`) lower on proxy than full.
- Record: 2 s at 30 fps writes 60 frames (ffprobe `nb_frames`), first/last frame equal to the live seek frames.
- `td_screenshot` of the controls window for the readability check, `td_errors` empty, `td_housekeeping` clean.
- T-46 check: composite is single compute-mode GLSL; verify no torn frames by sampling a crossfade frame twice.

### 2.7 Mac / 31550 caveats and fallbacks
- Op names confirmed in `ops/INDEX_2025.31550.json`: moviefileinTOP, moviefileoutTOP, cacheTOP, timelineCHOP, keyframeCHOP, audiofileinCHOP, audiospectrumCHOP, scriptCHOP/TOP/DAT, glslTOP, compositeTOP, textTOP, mathCHOP, limitCHOP, speedCHOP-class ops, chopexecuteDAT. Per-name check is a grep; actual create probes are part of the live step.
- Movie File In index-seeking on very long-GOP H.264 is slow and non-exact: use ProRes / Hap masters (our pipeline) or an All-Intra proxy. Fallback: Cache TOP ring buffer of a few frames.
- Four simultaneous 7488x2880 ProRes players will exceed a Rosetta/MoltenVK budget: the design uses proxies for editing and plays at most 2 full clips (crossfade) in a performance mode (`Maxplayers` par, default 2). Measure with `td_perf` before promising.
- Real-time recording is not trusted at big sizes: use stepped offline render; Hap/ProRes encode through `moviefileoutTOP` is unverified here (live test; fallback = write PNG sequence via script, encode with ffmpeg).
- Nothing audio-device related, so the default output remains the Mac speakers (audio file lane is *analysis only*, muted by default; to hear it, `audiodeviceoutCHOP` stays pointed at the built-in speakers).
- The `.toe` loaded in TD 2 is x86_64 under Rosetta; Python is 3.11 (numpy 2.1.2, cv2 4.11): pure Python logic needs nothing else.

### 2.8 Gated on newer builds (rows for docs/FUTURE.md)
| Idea | Gate |
|---|---|
| Timeline lanes as POP/channel-attribute animation (POP keyframing) | newer than 31550 if POP animation ops arrive; probe-gated |
| Native Animation COMP curve editor embedded in the lane view (replace our Script CHOP evaluation) | any build, probe-gated: dump an Animation COMP's tables first (AK live step 1) |
| Drop-frame (29.97) timecode and SMPTE LTC in | any build; idea only |
| AI audio tools (stems/beats/transcription) | cloud/paid in the original; ours: local `audiospectrumCHOP` beat lane now, a local model later |
| Frame-accurate GPU clip decode (hardware Hap Q multi-layer) | build-gated on Mac H.265/Hap decode behaviour; unverified |

## 3. Build time estimate
~4 h build + 1.5 h tests/live verification on a pilot (one clip, one lane), then clips/keys/record/panel in parallel lanes: Clock + logic + pytest (1 h, can run offline now), tables + players + compute composite (1.5 h), lanes + record (1 h), controls/ruler UI + window (1.5 h, the longest and the fiddliest: custom ruler). Total about **6-7 h**, ~4 h wall-clock if logic+tests, UI and record run as parallel lanes. Proxy generation (ffmpeg, background) per clip: seconds to minutes, not blocking.

## 4. Pointers for the sibling items the user listed (not researched here)
- **Face tracking** (vankrav): its description says "87 landmarks per face as named CHOP channels, eye/mouth openness, head roll, face/eyes/mouth masks; **Apple Vision on macOS, MediaPipe elsewhere**". That matches our own route: `jzb_camera_bridge` (arm64 Apple Vision helper over a Unix socket, `D_camera_mediapipe.md`) with a Script TOP/CHOP client in TD. TD's bundled Python 3.11 has **cv2 4.11.0, numpy 2.1.2, depthai** and no mediapipe/onnxruntime/pyobjc (read from site-packages, 26 Oct); Face Track CHOP/SOP are unsupported on this Mac (T-18). Test on `media/webcam/webcam_ref_5s.mp4` through a Movie File In TOP; live camera only when the user asks.
- **dB meter**: an In CHOP fed by the `AC_audio` COMP (default input), `analyzeCHOP` (RMS/peak) -> `mathCHOP` 20*log10 -> `lagCHOP` attack/release peak-hold, a GLSL/Rectangle bar view; output default stays the Mac speakers. 
- **Zerror, screen-reprojection, previz-stage**: separate notes.

## 5. Open questions for the user
1. Is a 4-player/2-full-clip performance cap acceptable, or must it be N full-res layers (needs a measurement on the Mac)?
2. Recording: offline stepped render only, or also real-time capture of the live output?
3. Should clip/key tables be importable from our PF26 `show.json` running order (acts -> clips)? That would tie it to the show timeline.
4. Skip the AI audio tools (we propose local beat lane only)?
5. If the user has a twozero account, the exact UI/params of the original could be seen from their app (we do not sign in); say so and we align naming.
