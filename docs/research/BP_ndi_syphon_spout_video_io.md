# BP - NDI, Syphon / Spout and video I/O routing for TouchDesigner on Mac + clean-room build spec (`BP_io_router`, `BP_io_probe`)

Researched 2026-10-26 (offline research run; nothing loaded into TD, no `jazib-td` tool called, no downloaded code run, no installs, no logins). Evidence tags: **[doc]** docs.derivative.ca / docs.ndi.video page fetched today, **[rel]** TD release notes page fetched today, **[forum]** derivative/Resolume/OBS forum thread, **[local]** read-only look at this Mac (`ls`, `lipo`, `strings`, `systemextensionsctl list`), **[ours]** our notes/LEARNINGS, **[mem]** my background knowledge, **UNVERIFIED** = needs a live probe. Target: TD **2025.31550** (`/Applications/TouchDesigner 2.app`, x86_64 under Rosetta, Vulkan/MoltenVK), macOS 27.0, M1 Max. General-purpose (PF26 not required). Licences are noted, not gating (user rule).

## 0. Findings in one screen

1. **Everything needed is already inside TD 2: no NDI runtime install, no Syphon install.** `Frameworks/libndi.dylib` = NDI SDK **6.2.0.3** (universal) and `Frameworks/Syphon.framework` (universal) ship in the app [local]. Release 31550 itself upgraded NDI to 6.2.0 and Spout to 2.007.014 [rel]. NDI Tools are **not** installed here and are not needed for TD<->Arena [local].
2. **What we already have:** `td_publish` / `td_publish_status` (Select -> Fit -> alpha step -> Null -> Syphon/NDI Out, inactive by default; T-61) and research AI/E (Arena side, alpha rule, bandwidth). **What is missing:** a *receive-side* and *routing* layer (NDI In / Syphon In / camera / movie into one switchable, alpha-normalised bus), a recorder with codec presets and exact frame counts (T-64), live status, and a **measured** latency + alpha probe. That is `BP_io_router` + `BP_io_probe`.
3. **Alpha is still the one open fact.** NDI SDK says RGBA/BGRA "is not pre-multiplied" (straight) [doc docs.ndi.video/docs/sdk/frame-types] while Resolume staff (2018) said Arena's NDI input accepted premultiplied only and a 2020s thread fixed TD->Arena NDI alpha fringes by matching the NDI library and toggling the clip *Alpha Type* [forum]; TD's NDI/Syphon pages say nothing about alpha [doc]; OBS shows the same TD-alpha confusion with the Syphon client [forum]. Outcome: **the COMP carries an explicit per-source and per-sink alpha mode (premult / straight / none), default premultiplied out (bundle rule), and the probe measures what a given receiver does.** No guessing.
4. **Syphon on this build is a black box.** TD's Syphon.framework headers list only the **OpenGL** server/client (no Metal server header) [local] while TD 2 renders through Vulkan/MoltenVK; a 2022 staff post said Syphon "not functional in the current experimental release" for the first Vulkan-era builds [forum]; fixes since: sender-name dependency (32280) and a stray extra `<name>_1` sender (33230) [rel]. It is 8-bit RGBA, same machine only [doc]. Never run between TD(Rosetta) and Arena here (E_live_rig) [ours]. First job of the probe: a TD-to-TD Syphon loopback must be bit-exact, then a foreign receiver (Arena / OBS) check (gated).
5. **NDI Out TOP crash on macOS at start-up was "attempted to be fixed" in 2025.32820** [rel] and NDI In had a hang on close with **NDI HX** sources (also 32820) [rel]. On 31550 treat the first NDI Out activation as crash-prone: save first (main session; T-71), never `destroy()` a live NDI In/HX op, set `active` off before delete.
6. **NDI In smeared/garbled textures on M1 at some resolutions** (1000x1000, 1080x2880 failed, 2880x1080 worked) was fixed in 2023.10000 [forum]; **16-bit NDI Out arrived as 8-bit on macOS** in 2021 ("limitation with NDI on macOS") [forum]. Both are cheap to re-test (L3, L4) before trusting `fixed16` or odd sizes (our 1080x1920 is exactly the failing family).
7. **Virtual camera on this Mac:** the legacy DAL route is dead (`/Library/CoreMediaIO/Plug-Ins/DAL` holds only `plugins-info.txt`; Syphon Virtual Webcam "no longer compatible with macOS Sonoma or later" [local, doc github.com/TroikaTronix/Syphon-Virtual-Webcam]). Working routes are **Camera Extensions**: OBS 32.1.2 is installed with its extension registered but `[activated waiting for user]` (needs the user to enable it in System Settings > Camera Extensions) [local], and NDI Tools' *Virtual Input* (needs NDI Tools = install gate) [doc]. TD has **no op that publishes a camera**; route = TD -> Syphon/NDI -> OBS (`mac-syphon.plugin`, `mac-virtualcam.plugin` present) -> any app [local].
8. **Video Device Out TOP = capture-card output only** (Blackmagic / AJA / Bluefish / Deltacast), **Video Stream Out TOP = Windows + NVIDIA only** [doc]. Neither is a Mac route; both are listed `available:false` with a FUTURE entry. **Video Device In (AVFoundation)** works (FaceTime HD, T-25) and will list any enabled camera extension [ours].
9. **Codecs for Arena clips** (Movie File Out, 31550 menu: rle, mjpa, mpeg4, h264, cineform, hap, h265, gif, notchlc, vp8, vp9, prores, vvc, av1 [local dump]): ProRes 4444 alpha is proven (ffprobe `ap4h yuva444p12le`, T-64); Hap family chunked x12, Hap Q = 1 B/px, Hap Q Alpha = 1.5 B/px [doc docs.derivative.ca/Hap]; **NotchLC has no confirmed Resolume playback** (only a VIDVOX user's guess) so it is not an Arena codec; macOS hardware H.264/HEVC encode arrived in 31550 (H.264/H.265 need Commercial/Pro licence) [rel][doc]. 33230 fixed "bad output for some codecs on macOS when inputs used a floating point pixel format" [rel] => on 31550 feed an 8-bit format to the encoder unless a 16-bit ProRes is wanted and verified.
10. **Latency has no published number anywhere** (NDI: "very low latency", 1080p60 up to 150 Mbps [doc]; Syphon: "almost no latency" vendor text [ours]); the only way is to measure: counter-in-picture + decode (Gray-coded bit strip, robust to lossy NDI), loopback inside TD, then via OBS/Arena (gated). Targets below are hypotheses to be replaced by numbers.

## 1. Landscape (ranked)

### 1.1 Built into 31550 (all [doc] unless noted; build tags from [rel])
| Rank | Op / feature | Mac / 31550 status | Notes |
|---|---|---|---|
| 1 | **Syphon Spout Out TOP** `syphonspoutoutTOP` | creatable; sender created inactive by `td_publish` (T-61) | pars `active`, `sendername`; 8-bit RGBA only; same machine; no size cap stated; `_1` stray-name bug fixed only in 33230 |
| 2 | **Syphon Spout In TOP** | same | par `sendername` (free text; no live server list on the page), `usespoutactivesender` is Windows |
| 3 | **NDI Out TOP** | NDI 6.2.0.3 in 31550; macOS start-up crash fix in 32820 | `active, name, failovername, fps, lowperformancebehavior (stallmainthread/skipframes), outputpixelformat (fixed8/fixed16), includealpha, grouptable, audiochop, metadata, outputcolorspace`; Info CHOP `num_connected, last_send_time, skipped_frames`; sends native NDI only (no HX) |
| 4 | **NDI In TOP / NDI DAT / Audio NDI CHOP** | NDI DAT clone crash and Audio-NDI fixes in 31550 | In pars `active, name, extraips, bandwidth (high/low), hwdecode (HX only), inputpixelformat (native/fixed8), inputcolorspace, grouptable, audiobuflen`; Info CHOP `receive_fps, queue_size, missed_frames, received_frames`; DAT lists sources with add/remove callbacks; metadata via Info DAT |
| 5 | **Video Device In TOP** (driver AVFoundation) | works (T-25 FaceTime HD); needs camera permission (`NSCameraUsageDescription` present [local]) | pars `driver, device, signalformat, inputpixelformat, transfermode, memorymode, deinterlace`; Info CHOP `signal_fps, capture_fps, frames_dropped, frame_queue_length`; virtual cameras appear as normal devices (page is silent, example "NDI Webcam Video 1") |
| 6 | **Movie File Out TOP** | ProRes alpha proven (T-64); HW H.264/HEVC on macOS since 31550 | see 2.5 |
| 7 | **Touch Out / Touch In TOP** | TD<->TD over TCP, `videocodec` uncompressed / HAP Q / HAP Q Alpha; same major release both ends; NotchLC streams only from 33070 | for a second TD (e.g. the native 2025.32820 app on this Mac, see 1.4) |
| 8 | **Video Device Out TOP** | cards only (Blackmagic/AJA/Bluefish/Deltacast); Sync Outputs needs Pro | `available:false` without a card |
| 9 | **Video Stream Out TOP** | "requires an Nvidia GPU and Windows" | RTMP/SRT/RTSP/WebRTC; not on Mac. WebRTC DAT route is the Mac-possible alternative (not researched) |
| 10 | **Screen Grab TOP** | exists; background-window grab is a Windows ctypes trick (community 67744 uses `ctypes.windll`) [local read] | on Mac use NDI Scan Converter (1.2) or SpectraBridge -> Syphon |

### 1.2 Mac tools around TD (nothing here installed unless stated)
| Tool | Role | Mac / current status | Licence |
|---|---|---|---|
| **OBS 32.1.2** (installed, arm64) | Syphon Client source (`mac-syphon.plugin`), NDI via DistroAV plugin (not installed), **OBS Virtual Camera** (camera extension, waiting for user), obs-websocket built in | [local] | GPL-2.0 [mem] |
| **NDI Tools for Mac** (ndi.video/tools; not installed) | Mac-only: **Scan Converter** (desktop/app capture to NDI, needs Screen Recording permission), **Video Monitor**, **Virtual Input** (NDI -> camera extension); both: Access Manager, Router, Test Patterns, Discovery [doc docs.ndi.video ... ndi-tools-for-mac-vs-windows]. Virtual Input has had a 6.1 issue + hotfix [doc]. Install = user gate | free, NDI EULA [mem] |
| **Syphon Recorder / Simple Client / Simple Server** (syphon.info; not installed) | the standard Syphon test pair; TD's page links the simple server | [mem] | BSD [mem] |
| **Syphon Virtual Webcam** (TroikaTronix) | Syphon -> OBS DAL virtual cam | **dead on Sonoma or later**, high CPU, MIT [doc] | MIT |
| **SpectraBridge** (bitstreammedia.com.au/spectrabridge; forum 998937) | any macOS window -> Syphon source, "native", 7-day trial, price/licence/latency not stated [forum] | UNVERIFIED on Rosetta TD; do not buy/install | commercial |
| **DistroAV** (OBS NDI plugin) | NDI in/out for OBS; needs NDI 6 runtime; 6.2.x for OBS 31.1.1+ [forum] | would need NDI runtime = install gate | GPL-2.0 [mem] |
| **Resolume Arena** (here 7.28.1 universal in `/Applications/Resolume Arena`; project rule: show host 7.23.2) | Syphon/NDI sources are "always enabled"; Sources tab; Arena publishes Syphon "Composition"/"Screen n" and NDI [doc resolume.com/support/en/NDI_inputs_and_outputs, kGqTF32cKRE transcript] | its `libndi.dylib` = NDI 6.1.1 (universal) [local] | n/a |
| **cansik/syphon-python** | PyObjC Syphon wrapper incl. Metal server | needs PyObjC: not available in TD's Python (T-19); only for a native helper | MIT [doc] |

### 1.3 Community assets (read-only; derivative.ca file URLs 403 to curl, not bypassed; some already expanded in `research_src/community/files`)
| Asset | What it is | Verdict |
|---|---|---|
| **RecordMovie COMP** (greg, 64788, `toeexpand`ed, text read) | wrapper over Movie File Out: Timer CHOP driven segmented recording (`onInitialize` record 0 + `n += 1`, `onTimerPulse` record 1, `onCycleEndAlert` record 0), `execute_recordOff` forces `record 0` on start/create/exit, audio gain/levels, `videocodec h265nvgpu` (Windows) | **borrow the pattern** (segment timer, always record-off on exit); no licence stated |
| **grabWindow.toe** (Simplo, 67744) | window grab via `ctypes.windll` + NDI In from "NEPTUNO (ndiChrome)" | Windows only; idea only (NDI Scan Converter on Mac) |
| **TDXvCon** (jpkelly, 75355; github.com/jpkelly/TDXvCon, pypi `tdxvcon`) | batch transcoder (NotchLC, HAP, HAPQ tags), "mac mentioned", built with Claude | not read, pip forbidden here; reference for a later `td_clip_bake` |
| **Video sync test wheel** (69246) / BB notes | sync-check wheel; frame counter method | idea reused in `BP_io_probe` |
| **Autosave tox** (61073) | autosave | superseded by T-71 |
| **iDepth NDI / iControl OSC & NDI / iXR** (fredfred, iOS apps) | phone as NDI source (also ZigCam) | useful NDI test sources; installs on a phone = user |
| **SimpleMixer** (github Richard-Burns/SimpleMixer, TD 2023.11290) | mixer with Syphon/Spout, RTMP, NDI out options [web] | not read; no router found. **No open-source NDI/Syphon router COMP was found**, so this spec is original |

### 1.4 Our own prior work (do not duplicate)
`handlers.py` `plan_publish` / `alpha_step` / `ndi_source_name` / `cmd_publish_status`; AI Patterns 1-5 and 10; E_live_rig sections 2-3 (bandwidth, Syphon vs NDI, Arena kill); BB section 5 (frame counter); T-43 (skipframes), T-61, T-64 (record frame count, never change cookRate live), T-46/T-47 (compute-mode GLSL if multi-pass), T-62 (StrMenu pars), T-67-T-71 (storage, destroy, autosave). Open FUTURE row: "NDI alpha on the wire and Syphon alpha in Arena" => this spec closes it with `BP_io_probe`.

Also on this Mac: **TouchDesigner.app is a second install, native arm64, build 2025.32820** [local] (NDI 6.3.1, NDI Out macOS start-up crash fix, ProRes 4:4:4:4 fix). Per the 7.23.2/31550 "no upgrade" stance it is only a comparison tool, and only with the user's go-ahead; the open T-46 question already asks the user about it.

## 2. How it works in TD on this Mac

### 2.1 NDI
- **Install/runtime:** none for TD (library in the app) [local]. Discovery is mDNS on the active network adapter; macOS "Local Network" privacy must allow TD (Arena doc: allow Resolume under Privacy; "NDI defaults to Wi-Fi on OSX, turn it off") [doc]. **Source names are `HOSTNAME (sender name)`**; `ndi_source_name(host, sender)` already exists in handlers. Same-machine loopback works for other receivers (OBS, Monitor, Resolume) [forum 441100]; a reboot fixed "localhost NDI dead for all apps" once [forum].
- **Alpha:** `includealpha` off = alpha 1.0 sent; on = RGBA path [doc]. Wire format meaning unknown (3). Arena: "Alpha Type" clip setting (Premultiplied default) and Advanced Output can drop alpha/bit depth to save bandwidth [doc/ours].
- **Bandwidth/format:** NDI High Bandwidth (SpeedHQ, lossy, intra-frame); Arena doc "a 60 fps 1080p stream needs at least 150 Mbps"; NDI white paper says up to 150 Mbps per 1080p60 stream and is "not deterministic" [doc]. Raw RGBA8 1080x1920@30 = 248.8 MB/s = 1.99 Gb/s, so NDI is roughly 13x compressed (arithmetic from the 150 Mbps cap at 60 fps; UNVERIFIED at our size). `fps` par: "lower values give higher image quality" [doc]. 16-bit: 2021 macOS limitation (L4).
- **HX:** NDI Out TOP and software NDI senders are **not HX**; NDI In `hwdecode` only helps H.264 HX sources (cameras/phones) [doc]; HX hang-on-close fixed in 32820 [rel]; NDI HX1 is "legacy, will be discontinued" [doc]. We do not send HX.
- **Stalls:** `lowperformancebehavior = skipframes` so a slow encoder never stalls the main thread (T-43). Multi-stream Mac receive glitches reported at 4x 4K from a BirdDog on 10G (Dante NIC interference, direct NIC fix) [forum 634607]: network, not TD.
- **Latency:** none published; In has `queue_size`; `bandwidth=low` selects the proxy stream (UNVERIFIED how this build maps it).

### 2.2 Syphon (and Spout)
- Shares an IOSurface-backed texture between processes on one Mac; no network; 8-bit RGBA [doc]. Spout is the Windows twin (Nvidia/AMD, 10 senders default, up to 32-bit float) and is the *same TOP* [doc]; this Mac only has Syphon, so the router keeps sender names Spout-safe (letters/digits/space/_.-, <= 63, same rule as `SENDER_NAME_RE`) and gates Spout-only items.
- Server appears in clients only while the sender is active (Resolume forum: "Syphon only works once at least one stream is open") [forum 58439, 89967]. Arena: Sources tab > Syphon servers, "just works like a clip" [kGqTF32cKRE]; Arena composition out: Output menu > Composition output sharing > Texture sharing Syphon; OBS: Syphon Client source > "Arena composition" [kGqTF32cKRE].
- **Orientation, alpha, name collisions, stale server after sender stops** are not documented; each is a probe (L2, L5, L7). Feedback trap: never route Arena's composition Syphon back into the same chain that feeds Arena (AI Patterns 5).
- A **Syphon server list** is not available to TD's Python (no PyObjC). Idea (gated, section 7): `tools/syphon_list.swift`, a 30-line Swift CLI (`swiftc` exists at /usr/bin) linked against TD's own Syphon.framework (`SyphonServerDirectory`), run by hand by the main session; or read the server list in OBS/Arena.

### 2.3 Video Device In / virtual cameras
- AVFoundation driver lists every `AVCaptureDevice`, including camera-extension virtual cameras (OBS Virtual Camera, NDI Virtual Camera) once the extension is enabled; permission = the camera prompt (already granted for TD 2, T-25). Pick by `menuNames` (T-25). Webcam tests use `media/webcam/webcam_ref_5s.mp4`, **never the live camera unless asked**.
- **Frame-rate/format:** `signalformat` menu from the device; capture-to-GPU transfer via `transfermode`/`memorymode`; Info CHOP `signal_fps`, `capture_fps`, `frames_dropped`. Camera latency (glass-to-glass) can't be measured by software alone (needs a screen+camera loop; gated).
- **TD -> camera app path (all gated, nothing started):** `Syphon Out "TD_x"` -> OBS scene with Syphon Client -> *Start Virtual Camera* -> Zoom/Meet/browser. OBS can be driven by obs-websocket (built in) from a WebSocket DAT; not built, section 6. Closing the loop for test: OBS Virtual Camera -> TD Video Device In -> `BP_io_probe` decode = measures the whole chain.

### 2.4 Alpha matrix (what we must keep straight)
| Place | Convention | Evidence |
|---|---|---|
| TD generators / Over TOP / composites | premultiplied by default (`premultrgbbyalpha`), since 2021.30000 | [forum 178001], AI Patterns 3 |
| Movie File In/Out ProRes 4444, Hap Alpha/Q Alpha | file alpha is stored as the encoder gets it; Arena clip `Alpha Type` decides how it is read | T-64 (ap4h yuva444p12le), AI 7 |
| NDI SDK BGRA/RGBA | "not pre-multiplied" (straight); UYVA/PA16 silent | [doc frame-types] |
| Arena NDI/Syphon input | Alpha Type default Premultiplied; staff 2018 "we only accept premultiplied at the moment on NDI" | [forum 65807 search snippet, AI] |
| OBS Syphon Client "allow transparency" | whole-image fade seen, no answer | [forum 153429] |
| **Router rule** | internal bus = premultiplied; per-source `Inalpha`, per-sink `Outalpha`, defaults premult/premult; measured by `BP_io_probe` against the actual receiver | this spec |

Un-premultiply is not a TOP (T-59 / AI): one GLSL pass `rgb / max(a, 1e-4)`; single pass, so pixel mode is safe (T-46); a **compute-mode** twin is kept for bigger chains.

### 2.5 Movie File Out presets for Arena and others (31550 menu from the op dump [local]; sizes from [doc Hap] and arithmetic)
| Preset id | videocodec / type | Alpha | Arena? | Bytes per frame at 1080x1920 (2.0736 Mpx) | At 7488x2880 (21.56 Mpx) |
|---|---|---|---|---|---|
| `hapq` | hap / Hap Q | no | yes (E) | 2.07 MB (1 B/px, before Snappy ~2:1) | 21.6 MB |
| `hapqa` | hap / Hap Q Alpha | yes | yes (UNVERIFIED in 7.23) | 3.11 MB (1.5 B/px) | 32.3 MB |
| `hap` / `hapa` | Hap / Hap Alpha | -/yes | yes | 1.04 / 2.07 MB | 10.8 / 21.6 MB |
| `prores4444` | prores / 4444 (`ap4h`) | yes | yes | big (~ 150-250 MB/s at 30 fps, UNVERIFIED) | realtime impossible (E) |
| `prores422hq` | prores / 422 HQ | no | yes | - | - |
| `h264hw` / `hevchw` | h264 / h265, macOS HW encode (31550) | no | proxies only; Commercial/Pro licence | - | - |
| `png_seq` | image sequence PNG (or EXR) | yes | via Alley/convert | - | - |
| `notchlc` | notchlc | yes | **not for Arena** (no confirmed support) | - | - |
| `dxv` | none in TD (T-11); Alley CLI (H-36) | - | native | - | printed Alley command only |
Rules: Hap is always chunked x12 in TD; `secondarycompression` off for extreme sizes (Hap doc); realtime encode of Hap Q at 7488x2880 is unproven (E) so offline mode (T-64 pump, `frames * cookRate / fps` cooks, never change `cookRate` live) is default for walls; feed the encoder `rgba8fixed` (33230 float bug); verify with ffprobe (`codec_name`, `pix_fmt`, `nb_frames` equal the request, alpha in pix_fmt).

### 2.6 Latency measurement (method, no hardware needed first)
- **Frame-number strip:** 32 cells (24-bit counter in **Gray code** + 8-bit CRC) 16 px wide across the bottom, white/black, centre-sampled, threshold = mid of the two reference cells; Gray code makes a wrong bit cost +-1 frame, CRC rejects garbage under lossy NDI. Receiver compares decoded counter with its own `absTime.frame` (same timeline) and a ms stamp for wall latency.
- **Stages:** (a) TD NDI Out -> NDI In in the same TD; (b) Syphon Out -> Syphon In in the same TD; (c) via OBS Syphon Client/virtual cam -> TD Video Device In (gated: OBS start + extension enable); (d) via Arena: Arena Syphon/NDI source -> Arena composition output -> TD (gated; AI T5/T6; film method in BB for glass-to-glass).
- **Report:** median / p95 / max frames, ms at the cook rate, duplicate and skipped counts, decode failure rate. Numbers are written to LEARNINGS (T-nn), never to a target table before measured.

## 3. CLEAN-ROOM BUILD SPEC A: `BP_io_router` (COMP path suggestion `/project1/lab/BP_io_router`)

**v1 built 26 Oct (31550), `builders/io_router.py` + `io_logic.py` + `test/test_io_logic.py` (15 offline tests):**
sources off/local/NDI In/Syphon In/movie/test, fit + alpha GLSL pass, A/B bus (manual / BPM cut), Syphon + NDI Out
sinks (inactive, read back `active` False x12), status/issues/routes tables, zkit panel. Live: alpha passes vs the numpy
reference max diff 0 (pass, straight->premult, premult->straight, drop alpha), bus Mix 0.5 vs average max 1 LSB, BPM cut
landed 0.0 frames from the beat boundary (120 bpm, 1 beat), ~1.8 ms/frame, project 60.2 fps. Not built yet: camera
source, record/touch sinks, NDI DAT discovery + follow, stale policy, audio fade, `BP_io_probe`; L1-L14 not run
(senders stay off until the user's go-ahead).

Builder `builders/io_router.py` (idempotent `build(parent)` like `db_meter.py`: reuse ops by name, keep custom par values and the panel), pure logic `builders/io_logic.py` (ASCII, no `td` import, numpy only), tests `test/test_io_logic.py`, host tool `tools/io_ffprobe.py` (stdlib; runs `/opt/homebrew/bin/ffprobe`, parses JSON). No Python functions in op storage (T-67). Safe-destroy rules T-70 (never `destroy()` something a window shows; NDI In/HX `active` off first). ASCII only. House rules: **self-contained** (custom pars drive internals, Out ops carry output only), own `controls` panel + `controls_window` opened by an `Opencontrols` pulse, **no built-in limits or warnings** (the status table reports facts; nothing blocks, nothing pops up), Mac speakers default audio out and **never mic -> speaker** (audio rides only if the user turns `Audio` on; the COMP never opens an audio device by itself), webcam tests only with the 5 s clip.

### 3.1 Interface
- Inputs: `in1..in4` In TOP (local sources), `in5` In CHOP (optional audio level for `Xfademode audio`), `in6` In CHOP (optional audio to attach to NDI Out).
- Outputs (output only): `out1..out4` Out TOP = the four normalised **source images** (premultiplied, sized), `out5` Out TOP = the **bus** (what `bus` sinks send), `out6` Out CHOP `stats`, `out7` Out DAT `status` (one row per source and sink: kind, name, active, res, fps, queue, missed, skipped, cookms, stale, alpha, note).

### 3.2 Custom parameters (page, name; names = one capital then lowercase/digits; T-62: StrMenu pars are free text, bind by expression only after checking)
- **Sources** (x4, `S1..S4`): `S1kind` menu off / local / ndi / syphon / camera / movie / probe; `S1name` str (NDI source name or Syphon sender); `S1match` str (substring/regex to auto-follow a source whose host prefix changes); `S1follow` toggle (poll the NDI DAT every 1 s and reconnect); `S1active` toggle; `S1inalpha` menu premult / straight / none / auto-ndi (auto = use the probe's measured result when present, else straight for NDI, premult for Syphon, flagged as assumption in `status`); `S1res` menu input / 1080x1920 / 1920x1080 / 3840x2160 / custom + `S1resw/h`; `S1fit` menu fitbest / fill / native; `S1bw` menu high / low (NDI); `S1hx` toggle (hwdecode, HX only); `S1extraips` str; `S1group` str; `S1dev` menu (Video Device In devices, by menuNames); `S1file` file (movie); `S1loop` toggle.
- **Sinks** (x4, `O1..O4`): `O1kind` menu off / syphon / ndi / record / touch; `O1src` menu S1 / S2 / S3 / S4 / bus; `O1name` str (sender name; default `TD_<comp>_<n>`); `O1active` toggle (default off: a sender is the user's go-ahead); `O1res` as sources; `O1outalpha` menu premult / straight / none; `O1fmt` menu fixed8 / fixed16 (NDI only; Syphon is 8-bit); `O1fps` float (0 = cookRate); `O1skip` toggle (NDI skipframes, default on); `O1failover` str (NDI failovername); `O1port` int (Touch Out); `O1codec` menu = preset ids of 2.5 (record); `O1file` file + `O1stamp` toggle (append timestamp); `O1recmode` menu free / frames / segments; `O1frames` int; `O1seglen` float (s); `O1rec` toggle (record).
- **Bus**: `Busa` / `Busb` menu S1..S4; `Mix` float 0-1 (slider only, field unclamped); `Xfademode` menu manual / bpm / audio; `Bpm` float 120; `Cutdiv` menu 1/4 / 1/2 / 1 / 2 / 4 beats (cut is quantised to the next division); `Xfadetime` float s; `Cutnow` pulse; `Fadecurve` menu linear / smooth.
- **Failover/stale**: `Stalesec` float 1.0 (the "stale" flag threshold, informational); `Stalepolicy` menu none / hold / black / alt; `Altsrc` menu S1..S4 (only used by `alt`). Default `none`: nothing changes automatically.
- **Controls**: `Opencontrols` pulse, `Bypass`, `Resetdefaults` pulse, `Refreshsources` pulse, `Audio` toggle (default off).
- Read-only: `Ndicount` (sources visible), `Fps1..4`, `Skipped1..4`, `Staleflag`.

### 3.3 Internal network (L-to-R stages, titled boxes, role colours, comments; `td_layout stages`)
1. **"Discovery"**: `ndi_list` (NDI DAT, callbacks for add/remove), `ndi_state` (Table DAT filled by callbacks), `matcher` (Text DAT with `io_logic.match_source`), `devices` (Table DAT from `videodeviceinTOP.par.device.menuNames`, refreshed by `Refreshsources`).
2. **"Sources"** x4: `s{n}_ndi` NDI In, `s{n}_syp` Syphon In, `s{n}_cam` Video Device In, `s{n}_mov` Movie File In (looped), `s{n}_loc` Select of `in{n}`, `s{n}_probe` (the `BP_io_probe` instance or its pattern TOP), `s{n}_sel` Switch TOP (index from `S{n}kind`) -> `s{n}_fit` Fit TOP -> `s{n}_alpha` (alpha-normalise, 3.5) -> `s{n}_out` Null. Unused kinds are bypassed/inactive (NDI In `active` off so there is no network cost).
3. **"Health"**: per source `s{n}_info` Info CHOP (NDI: queue/missed/fps; camera: signal_fps/dropped), `s{n}_hash` (TOP 8x8 resample -> TOP to CHOP) + Script CHOP `stale` (counts seconds the 64 values are identical, 5 s history; static pictures are legitimately "stale", the flag is information), Execute DAT 1 s tick that applies `Stalepolicy` and the NDI follow logic.
4. **"Bus"**: `bus_a`, `bus_b` Select TOPs -> Cross TOP `bus_x` (index = `Mix` or the automatic fade) -> `bus_out`; fade state machine (`io_logic.bus_step(state, dt, mode, bpm, div, audio)`) in a Script CHOP `bus_ctl`; `Cutnow` and beat quantisation (`next_boundary(t, bpm, div)`).
5. **"Sinks"** x4: `o{n}_pick` Switch (S1..S4/bus) -> `o{n}_fit` -> `o{n}_alpha` (3.5) -> `o{n}_fmt` Null (pixel format `rgba8fixed` or `rgba16float` for fixed16) -> exactly one active sender among `o{n}_syp` (Syphon Out), `o{n}_ndi` (NDI Out: `skipframes`, `fixed8`, `includealpha` from `Outalpha != none`), `o{n}_rec` (Movie File Out via the preset table), `o{n}_touch` (Touch Out); inactive senders are `active 0`. Info CHOPs for `last_send_time`, `skipped_frames`, `num_connected`.
6. **"Status"**: Script DAT `status` assembles the table from all Info CHOPs + `io_logic.build_status`; `stats` CHOP for the panel meters.
7. **"Controls"**: `controls` container (custom-par widgets, source/sink strips with a thumbnail Null each, status table, bus fader, big record buttons) and `controls_window`; `Opencontrols` pulse opens it (Basic Widgets are fine on TD 2, T-52).

### 3.4 Data formats
- `routes` (Table DAT, generated, one row per sink): `sink kind src name res outalpha fmt active` - the same table the MCP tool `td_io_route` reads/writes.
- `status` columns: `id kind name active w h fps queue missed skipped cookms stale alpha note`.
- Probe results are stored in a Table DAT `measured` (`pair`, `alpha_model`, `latency_median_f`, `p95`, `date`), read by `auto-ndi`.

### 3.5 Alpha conversion stage (one GLSL TOP pass, pixel mode is safe single-pass; compute twin for chains)
```glsl
// uniform int uMode; // 0 premult->straight, 1 straight->premult, 2 drop alpha (over black, premult in), 3 drop alpha (straight in), 4 passthrough
out vec4 fragColor;
void main(){
  vec4 c = texelFetch(sTD2DInputs[0], ivec2(gl_FragCoord.xy), 0);
  if (uMode==0) c = vec4(c.a>1e-4 ? c.rgb/c.a : vec3(0.0), c.a);
  else if (uMode==1) c = vec4(c.rgb*c.a, c.a);
  else if (uMode==2) c = vec4(c.rgb, 1.0);              // already premultiplied: over black = rgb
  else if (uMode==3) c = vec4(c.rgb*c.a, 1.0);
  fragColor = TDOutputSwizzle(c);
}
```
Mode index is `io_logic.alpha_mode(src_alpha, dst_alpha)` (same table as `alpha_step` in handlers; reuse, do not fork).

### 3.6 Python logic (`io_logic.py`, pure + numpy, offline-testable)
- `alpha_mode(src, dst)`; `convert_alpha(rgba8, src, dst)` numpy reference with round-half-up and a=0 safe; `composite(rgba8, bg8, model)` where model is `premult` (`rgb + bg*(1-a)`) or `straight` (`rgb*a + bg*(1-a)`).
- `classify_alpha(readback_rgb8, src_rgba8, bg8)`: least-squares fit of both composite models to a receiver's readback of the alpha ramp; returns `{model, err_premult, err_straight, confident}`. This is what turns the Arena/OBS check into a number.
- `ramp_rgba(w, h, steps)`: the test source (horizontal alpha ramp 0..1 of white and of saturated colours, over a checker so fringes show).
- `gray_encode/decode`, `crc8`, `encode_strip(n, ms, cell, width)`, `decode_strip(rgb8_row, cell, width)` -> `(n, ms, ok)`, threshold from the two reference cells; tolerant to blur, +-24 LSB noise, 8-bit quantisation, 2-pixel shifts.
- `latency_stats(samples)` (median/p95/max in frames and ms, duplicates, skips from decoded-counter deltas, decode failure rate, jitter).
- `ndi_source_name(host, sender)`, `match_source(names, pattern, prefer_host)`, `plan_routes(config)` (normalises 4x4 config, **reports** duplicate sender names per kind, a sink whose source is fed by its own loopback, and missing files - report only, never blocks).
- `estimate_bandwidth(w, h, fps, fmt)` (raw RGBA8/16f, NDI cap 150 Mbps per 1080p60 scaled by pixels as a *rough* guide, Hap/HapQ/HapQA bytes/frame from the Hap doc, ProRes = unknown -> `None`).
- `RECORD_PRESETS` (id -> Movie File Out par dict: `videocodec`, `videocodectype` token, `moviecontainer`, `videopixelformat`, `secondarycompression`, format to feed) and `pump_cooks(frames, cook_rate, fps)` (T-64: `frames * cook_rate / fps`, ceil).
- `ffprobe_report(json_text)` -> `{codec, pix_fmt, frames, fps, has_alpha, w, h}` and `check_clip(report, expect)`; alpha if `pix_fmt` has `a` in an alpha family (`yuva*`, `rgba*`, `bgra*`, `argb*`).
- `bus_step`, `next_boundary`, `fade_curve`.

### 3.7 Offline tests (pytest, `test/test_io_logic.py`, no TD, no network)
1. Alpha: premult->straight->premult exact for a=255, max error <= `ceil(255/(2a))` for a<255; a=0 gives rgb 0 not NaN; premult ramp satisfies `max(rgb) <= a`; `alpha_mode` table equals `alpha_step` outcomes for all 9 pairs.
2. Composite/classify: synthesise readbacks from each model (+-2 LSB noise) and recover the model with `confident` true; an ambiguous (alpha all 255) ramp returns `confident` false.
3. Strip: encode counters 0..2^24-1 sampled (edge cases around powers of two); decode after Gaussian blur sigma 1.5 px, +-24 noise, 8-bit requantise, JPEG-like block smoothing, 1-2 px shift: 100 % recovered with CRC, wrong CRC rejected; Gray property (adjacent counters differ in one bit).
4. `latency_stats` on synthetic series with known duplicates/skips; p95 correct.
5. `estimate_bandwidth`: 1080x1920@30 RGBA8 = 248,832,000 B/s; Hap Q 2,073,600 B/frame; Hap Q Alpha 3,110,400; 7488x2880 Hap Q = 21,565,440 B/frame; 60 fps doubles.
6. `pump_cooks(30, 60, 30) == 60` (T-64 numbers); `RECORD_PRESETS` keys complete and each names a codec token present in the 31550 menu list.
7. `ffprobe_report` on three fixture JSONs (ProRes 4444 `yuva444p12le` alpha true; Hap `hap_q` no alpha; H.264 `yuv420p`), `check_clip` mismatch messages.
8. `match_source`: host prefix change `"MAC-A (Cam)"` vs `"MAC-B (Cam)"`, regex vs substring, none found.
9. `plan_routes`: duplicate names reported, never raising; loopback detection.

### 3.8 Live verification (31550; numbers to hit; **nothing needs Arena/OBS/hardware until L9**)
Main session saves before L1 (T-71) and keeps the COMP in `/project1/lab`; one live lane only (T-42).
| Id | Test | Pass / record |
|---|---|---|
| L1 | TD NDI Out -> NDI In (same TD), `BP_io_probe` 1080x1920, fixed8, 30 fps, 600 frames, `skipframes` | decode OK >= 99.5 %, `skipped_frames` 0; **record median/p95 latency in frames and ms** (hypothesis <= 3 frames) |
| L2 | Syphon Out -> Syphon In, same TD, opaque probe | byte-identical (max abs diff 0) or the exact diff recorded; latency recorded (hypothesis 0-1 frame); orientation of the F marker recorded |
| L3 | Sizes through NDI and Syphon: 1000x1000, 1080x1920, 1920x1080, 2880x1080, 3840x2160, 7488x2880 | no smear (decode OK, strip + F marker correct); cook ms and fps recorded; breaks listed |
| L4 | `fixed16` NDI with a 16-bit float ramp | readback levels > 256 distinct or confirmed 8-bit; settles the 2021 macOS limitation on 31550 |
| L5 | Alpha ramp through NDI (includealpha) and Syphon, same TD | readback model recorded (`classify_alpha`); because both ends are TD, the *foreign* receiver result stays "not checked in Arena/OBS" until L9 |
| L6 | NDI discovery: sender appears as `HOST (name)` in `ndi_list` within <= 3 s; rename -> remove+add callbacks; two senders with the same name -> behaviour recorded; `S1follow` reconnects after a sender restart in <= 3 s | table of observed timings |
| L7 | Syphon `_1` duplicate (33230 fix): after toggling `active` 10x and renaming, count senders visible to the (gated) Swift lister or OBS | observed count recorded (deferred to L9 if no lister) |
| L8 | Record presets (2 s, exactly 60 frames at 30 fps, offline pump) at 1080x1920: `prores4444`, `prores422hq`, `hapq`, `hapqa`, `hap`, `h264hw`, `png_seq` | ffprobe frames == 60, `pix_fmt` as expected, alpha flags, file size vs section 2.5 (+-30 %), TD fps unchanged; `hapq` decoded back through Movie File In and compared (mean abs diff <= 3 LSB); realtime encode speed (x of realtime) at 1080x1920 and 7488x2880 recorded; `cookRate` never touched during a take |
| L9 | **Gated (user go-ahead each):** Arena scratch comp: pick the TD Syphon and NDI sources; alpha ramp over mid-grey with Alpha and Add blends; read Arena "Composition" Syphon back into `BP_io_probe`; F orientation; latency Arena-in to Arena-out; OBS Syphon Client + Virtual Camera -> TD Video Device In chain | `classify_alpha` results written to LEARNINGS and FUTURE row "NDI alpha on the wire" closed |
| L10 | NDI Out crash check: 20 cycles of `active` on/off, rename while active, delete while inactive, after a main-session save | no TD crash/hang (31550); result recorded (32820 says it attempted a fix) |
| L11 | Slow-encoder behaviour: 3 NDI Outs at 3840x2160 on `skipframes` | TD fps >= 55 at cookRate 60, `skipped_frames` grows, no stall |
| L12 | Stale/failover: stop a sender: `stale` flag rises within `Stalesec` + 1 s; policy `hold` keeps last frame, `black` blanks, `alt` switches; `none` changes nothing | pass |
| L13 | Bus: manual Mix, `bpm` quantised cut lands within 1 frame of the beat boundary, `audio` mode follows `in5` level | pass |
| L14 | Persistence: rebuild with the builder on a clean `lab` gives identical ops/pars; the COMP saved as `.tox` (main session via `td_tox_save`) loads back | idempotent |

### 3.9 Performance targets (hypotheses until measured) and Mac caveats
- Router overhead with 4 idle sources and 4 inactive sinks < 0.3 ms cook; one Syphon sink at 1080x1920 < 1 ms CPU (copy is GPU); NDI sink cost is CPU encode on its own thread (`last_send_time`) - record it at each L3 size; TD fps holds at cookRate with the panel open.
- Memory: each full-res source and sink Null at RGBA8 1080x1920 = 8.3 MB; 7488x2880 RGBA8 = 86.3 MB per TOP (E): the router does not cache extra frames; bus uses one Cross TOP.
- Keep NDI on a wired/loopback path, Wi-Fi off (Arena doc); allow TD under System Settings > Privacy > Local Network and Camera as needed; Screen Recording only for NDI Scan Converter (not installed).
- Alpha 8-bit on the wire everywhere except NDI `fixed16` (probe L4); Hap/ProRes masters can be 10/12-bit.
- Never `destroy()` a live NDI In (HX hang, T-70); never change `cookRate` live (T-64); no multi-pass GLSL pixel chains beyond the single alpha pass (T-46).

### 3.10 Persistence and housekeeping (user: "save ur projects always so u dont loose ur progress or learnings or node setups")
- The builder + `io_logic.py` + tests + `tools/io_ffprobe.py` are the node setup of record (idempotent rebuild); the live `.toe` is secondary.
- The builder agent never saves the project (T-71): it reports "ready to save" + COMP path; the main session runs `td_save_project` and `td_tox_save` for `BP_io_router` and `BP_io_probe` to `output/` (convention of the other builders) **before the first NDI/Syphon activation (L1/L10)** and after each verified build. The handlers autosave (10 min, newest 5) still runs.
- Every bug gets a LEARNINGS T-nn at once; probe numbers from L1-L8 go into this file's section 5 (open questions closed) the same session; FUTURE rows updated.

## 4. CLEAN-ROOM BUILD SPEC B: `BP_io_probe` (`/project1/lab/BP_io_probe`, small, built first; also usable standalone and as source kind `probe`)

Builder `builders/io_probe.py`, uses `io_logic` encode/decode. Self-contained rules as in A.
- Custom pars: `Mode` menu send / receive / both; `Resx/Resy` (default 1080x1920); `Pattern` menu counter / alpharamp / bars / orient / allinone; `Cell` int 16; `Fps` read-only; `Reset` pulse; `Windowframes` int 600 (stats window); `Opencontrols` pulse; receive: `Source` TOP ref (default `in1`), `Lockoffset` toggle.
- Network: `gen` GLSL TOP (single pass: counter strip bottom, bars, 0..255 ramp, horizontal alpha ramp of white + saturated colours over a checker, an asymmetric **F** glyph + corner marks + top-left arrow for orientation), `counter_cells` Script CHOP (writes the 32 cells for the current frame via `encode_strip`), `out1` Out TOP. Receive: `rd` Script CHOP reading the bottom rows of `Source` with `numpyArray(delayed=True)` after a force-cook (T-13), `decode_strip`, `stats` CHOP (latency_f, latency_ms, dup, skip, fail, fps) + Table DAT history; `out2` Out CHOP.
- Offline logic is exactly `io_logic` (tests 3.7 #3-#4). Live: L1-L3, L5, L9.
- It is the probe the FUTURE row "NDI alpha on the wire / Syphon alpha in Arena" asks for: the `alpharamp` pattern + `classify_alpha`.

## 5. Open questions (for the first live probes, not for the user)
- Which Syphon server API TD 2 uses on Vulkan (OpenGL server header only); does a foreign client see our texture upright; is a stale server removed when `active` goes off.
- NDI `includealpha` wire format (straight vs premultiplied) and what NDI In returns; Arena's reading (L5/L9).
- Does `fixed16` survive on macOS 31550; are 1080x1920 and 1000x1000 clean.
- Does the Video Device In menu list the OBS Virtual Camera once enabled; latency camera-extension chain.
- Does `S1bw=low` really select the proxy stream; does the NDI DAT list the local sender immediately.
- Hap Q Alpha / ProRes 4444 playback of our files in Arena 7.23 (hand test, gated).
- NDI Out start-up crash on 31550 (L10); Syphon extra `_1` name on 31550 (L7).
- Is H.264 hardware encode allowed under this TD licence (docs say Commercial/Pro).

## 6. MCP tool ideas (for `src/`, later; none built now)
- **`td_io_list`** (read-only): every Syphon/NDI/Video Device/Movie/Touch op in the project with name, active, res, fps, Info stats (superset of `td_publish_status`); live NDI DAT source list; Video Device In `menuNames`; duplicate sender names; plus *host* facts the server gathers itself without TD: `systemextensionsctl list` (camera extension state), `lipo -archs` of TD/Arena/OBS, `libndi` versions (`strings`), listening ports of TD (`lsof -a -p <pid> -i`). Returns `available:false` rows (Video Device Out, Video Stream Out, Spout) with reasons.
- **`td_io_route`** {sources[], sinks[], matrix, active:false, build?:true}: builds/updates `BP_io_router` (or only the `routes` table), returns the exact names to pick in Arena/OBS and the `td_io_probe` command to run; flipping `active` on a sender stays the user's go-ahead (as `td_publish`).
- **`td_io_probe`** {pair: ndi|syphon|obs|arena, size, frames}: runs L1-L5 shapes and returns the latency/alpha table; `arena`/`obs` pairs refuse unless the user said go.
- **`io_check_file`** {path, expect}: host-side ffprobe check (frames, pix_fmt, alpha) = `ffprobe_report` + `check_clip`; later feeds `td_clip_bake` (FUTURE).
- **`td_obs_cam`** (gated idea): obs-websocket start/stop Virtual Camera and set a Syphon Client source name.

## 7. Gated items for `docs/FUTURE.md` (proposed rows; the main session adds them)
| Item | Build gate | Status | Where | Test to unlock |
|---|---|---|---|---|
| Video Device Out TOP (SDI/HDMI cards) in the router | any build (hardware-gated) | idea only | BP 1.1 | a Blackmagic/AJA device on the Mac |
| Video Stream Out (RTMP/SRT/RTSP, NVIDIA) and WebRTC DAT video route | Windows+NVIDIA; WebRTC untested | idea only | BP 1.1 | Windows host, or a WebRTC probe |
| Spout sinks/sources in the router | Windows only | kept name-compatible; no code | BP 2.2 | Windows host |
| NotchLC over Touch Out/In; NotchLC decode 16-bit float | 2025.33070+ | recorded | BP 2.5, release notes | newer build |
| NDI 6.3.1, NDI Out macOS start-up crash fix, HX hang fix | 2025.32820+ | recorded | BP 0 / release notes | native arm64 `TouchDesigner.app` comparison (user's go-ahead) |
| Syphon `_1` stray sender fix; Movie File Out float-input fix on macOS | 2025.33230 | recorded; our workaround = 8-bit feed | BP 0 | L7, L8 |
| Syphon server lister (`tools/syphon_list.swift` against TD's Syphon.framework) | any build | idea only: compiling native code = user's go-ahead | BP 2.2 | user OK, then run by hand |
| NDI Tools (Scan Converter, Virtual Input) install | n/a | install gate | BP 1.2 | user OK |
| OBS Virtual Camera extension enable + OBS control by obs-websocket | n/a | user action in System Settings | BP 2.3 | user enables extension |
| DistroAV (NDI inside OBS) | install gate | idea only | BP 1.2 | user OK |
| `td_io_list`, `td_io_route`, `td_io_probe`, `io_check_file` | 31550 | ideas | BP 6 | after builders pass L1-L8 |
| Arena-side alpha / orientation / latency (L9) | Arena 7.23.2 | not run | BP 3.8 | user go-ahead per Arena call |
| `td_clip_bake` (existing row) now has the preset table and ffprobe checker to reuse | 31550 | recipe + BP presets | BP 2.5 | second use |

## 8. Builder job description (hand to the builder agent)
Build two self-contained Base COMPs in `/project1/lab`: first `BP_io_probe` (a TD test-pattern and decode COMP: Gray-coded 32-cell frame counter + CRC strip, 0-255 ramp, bars, alpha ramp over checker, asymmetric F marker; in receive mode it decodes a TOP and reports latency in frames/ms, duplicates, skips and decode failures) and then `BP_io_router` (an I/O router: four sources, four sinks, one bus). Start offline: write `builders/io_logic.py` (alpha conversion and `classify_alpha`, composite models, Gray/CRC strip encode+decode, `latency_stats`, NDI name matching, route planning that only reports, bandwidth and Hap sizing, Movie File Out preset table with `pump_cooks`, ffprobe report/check, bus step and beat quantisation) with `test/test_io_logic.py` covering 3.7 (run `npm test` or pytest offline), and `tools/io_ffprobe.py` (stdlib, `python3 -I`, wraps `/opt/homebrew/bin/ffprobe -show_streams -of json`). Then write `builders/io_probe.py` and `builders/io_router.py` (idempotent like `db_meter.py`; stage boxes via `td_layout stages`; safe-destroy rules T-70; T-62 for StrMenu pars; ASCII only): custom pars of 3.2 and 4, networks of 3.3 (Sources, Health, Bus, Sinks, Status, Controls), one GLSL alpha pass (3.5), `controls` + `controls_window` opened by `Opencontrols`, Out ops output only, no limits, no warnings, no audio device opened. Keep every sender inactive (`active` false read back) until the main session says go; never start Arena, OBS or NDI Tools, never use the live camera (use `media/webcam/webcam_ref_5s.mp4`), never save the project (report "ready to save"), never change `cookRate` live. Run live tests L1-L8 and L10-L14 in one lane (T-42), write numbers into this file's section 5, one LEARNINGS T-nn per bug, update docs/research/README.md and FUTURE.md, and leave L9 (Arena/OBS) for the user's go-ahead.

## 9. Sources
Docs (fetched 26 Oct 2026): docs.derivative.ca/NDI_In_TOP, /NDI_Out_TOP, /Syphon_Spout_In_TOP, derivative.ca/UserGuide/Syphon_Spout_Out_TOP, /Video_Device_In_TOP, /Video_Device_Out_TOP, /Video_Stream_Out_TOP, /Touch_Out_TOP, /Movie_File_Out_TOP, /Hap, /Release_Notes (builds 2025.30000-2025.33230); docs.ndi.video/docs/sdk/frame-types, /all/getting-started/white-paper/bandwidth.md, /all/using-ndi/ndi-tools/ndi-tools-for-mac-vs-windows, /ndi-tools-for-mac/virtual-input; resolume.com/support/en/NDI_inputs_and_outputs.
Forum: forum.derivative.ca/t/syphonspout-not-working-on-mac/234898, /t/ndi-16bit-issue-on-mac-osx/231022, /t/fixed-ndi-in-top-broken-texture-mac-m1/377558, /t/ndi-in-broken-on-apple-silicone-m1/441100, /t/ndi-recording-on-mac/634607, /t/fixed-alpha-premultiplication-issues/178001, /t/export-video-with-transparency/276167, /t/spectrabridge-get-any-macos-window-into-td-as-a-syphon-source-low-latency/998937; resolume.com/forum viewtopic p=65807, 78610, 78441, 79501 (403 to fetch; snippets only), 58439, 89967, 60948; obsproject.com/forum/threads/alpha-channel-in-obs-from-touchdesigner.153429; github.com/TroikaTronix/Syphon-Virtual-Webcam; github.com/cansik/syphon-python; github.com/vidvox/hap; github.com/Richard-Burns/SimpleMixer; derivative.ca/community-post/asset/tdxvcon-video-transcoder/75355.
YouTube (auto subtitles, `yt-dlp --skip-download`, two requests, no 429): kGqTF32cKRE "Resolume Arena Tutorial - Syphon" (Resolume), Bc1lR8JzfJk "NDI Tools for Immersive Experiences - TD Tutorial 097" (The Interactive & Immersive HQ; Windows-centred); saved in `research_src/BP_ndi_syphon_spout_video_io/yt/` (text only).
Local read-only: TD 2 and TD.app `Info.plist`/`lipo`/`Frameworks` (libndi 6.2.0.3, Syphon.framework headers), Arena `libndi.dylib` 6.1.1 and Info 7.28.1, OBS 32.1.2 plugins, `systemextensionsctl list` (OBS camera extension waiting for user), `/Library/CoreMediaIO/Plug-Ins/DAL`, `ops_TOP_2025.31550.json` (Movie File Out menus), community `recordMovie.5.tox` and `grabWindow.toe` (expanded text), `INDEX_2025.31550.json`.
Our notes: AI (Patterns 1-5, 7, 10, T5), E (sections 2-3), BB (section 5), T (T-18, T-19, T-25, T-43, T-46, T-47, T-52, T-59, T-61, T-62, T-64, T-67-T-71), FUTURE row "NDI alpha on the wire".
