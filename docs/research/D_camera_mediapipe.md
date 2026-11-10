# D - Camera inputs, MediaPipe and other vision routes in TouchDesigner 2025.31550 (research, 16 Oct 2026)

Agent D for the lead. Build **2025.31550**, `/Applications/TouchDesigner 2.app` (x86_64 under Rosetta), M1 Max, macOS reported as 27.0, Pro licence.
Research only: nothing installed or downloaded, no camera/NDI/Syphon started, nothing built for the show.
Notation: **probed** = ran live in 2025.31550 via `td_exec` (expression given); **bundle** = read from the install on disk;
**doc** = URL (or "in-build doc" = the offline help shipped inside `TouchDesigner 2.app/Contents/Resources/tfs/Samples/Learn/OfflineHelp/`, so it matches this build);
**unverified** = memory, older build, vendor claim or untested. No reference images were saved (nothing needed), so there is no `refs/D_camera/`.

## Short answer
1. **On this Mac the useful built-ins are few.** Probed: Body Track CHOP, Face Track CHOP/SOP, Optical Flow TOP, NVIDIA Background TOP, NVIDIA Upscaler TOP, Kinect/Kinect Azure/ZED TOPs, RenderStream In, ST2110 In
   all report **"This node is not supported on this operating system"** on creation. The in-build docs say Windows-only (+ NVIDIA RTX) for the first four. Orbbec, RealSense, OAK, Ouster, Blob Track (OpenCV) create without that error.
2. **MediaPipe in TD = Torin Blankensmith's plugin, latest `v0.6.0` (published 2026-10-14, two days ago), MIT.** It runs MediaPipe JS/WASM+WebGL in a Chromium page inside a **Web Render TOP**, and the camera is opened **by the web page** (`getUserMedia`),
   not by Video Device In. Its stated test builds: `TD 2023.11880` and "TD 2025.xxxxx" (placeholder) for v0.6.0; **`TD 2025.31500` for v0.5.2**, `TD 2025.33070` for v0.5.3. Nobody states 2025.31550, Rosetta or Apple-silicon-vs-Intel anywhere. **Untested here.**
3. **The camera permission is the likeliest blocker** (macOS 27, Rosetta app, camera opened from a CEF helper process). `TouchDesigner 2.app`'s Info.plist has `NSCameraUsageDescription` = "Required for Video Device In TOP."; the five Web Render Helper apps have no usage string.
   Open issues in the plugin repo (#140, #170, #165, #158) and a Derivative forum bug (Jan 2026) show Mac users getting a black camera / "Webcam failed to start" / error -108. Whether it works under Rosetta here is **unverified**; it needs one user-approved test.
4. **Reliable camera routes that need no permission fight:** a **Syphon/NDI feed from Resolume/OBS**, or a capture card (UVC, AJA/Blackmagic via the bundled drivers). Probed: `videodevicesDAT` lists exactly one device, `FaceTime HD Camera` (AVFoundation). Enumerating needed no prompt.
5. **TD's own Python already has OpenCV 4.11.0 (x86_64), NumPy 2.1.2, `depthai`** (bundle, probed). No `onnxruntime`, `mediapipe`, `torch`, `coremltools`, `pyobjc`, `python-osc`. **Verified recipe:** Script TOP + `cv2.calcOpticalFlowFarneback` gives correct motion
   (measured ~42 ms per cook at 640x360 in, 320x180 flow, with other work running; see recipe 2). So optical flow, background subtraction and blob tracking work on CPU without any plugin.
6. **ML models (pose, face, segmentation, depth) on Apple silicon are best run in a native arm64 helper process** (td-port's `jzb_camera_bridge` already does Apple Vision person-mask, faces and Depth Anything V2 over a Unix socket; standalone numbers below, never run inside TD).
   Reason: PyPI only ships arm64 wheels for the newest `mediapipe` (1.1.1) and `onnxruntime` (1.31.0) on macOS; the last x86_64 macOS wheels are `mediapipe 0.10.21` (needs `numpy<2`, TD ships 2.1.2) and `onnxruntime 1.23.2` (PyPI JSON, below).
7. **For PRISMFEST'26 the venue camera plan is still open** (`prismfest26-show/RUNTIME.md`: "how many cameras, clean feeds to FOH, latency"; the organiser provides cameras and clean feeds). Anything that needs the real feed (IMAG on L1/R1, crowd cam) cannot be finished before that arrives;
   hands, silhouettes, optical-flow and face tools can all be prototyped on the Mac's FaceTime camera or a recorded clip.
8. Rule that shapes all of it (RUNTIME layer 6): a live layer **must fail safe**. TD's output goes over Syphon on layer 6; "reactive loss -> base loop keeps running"; camera loss -> C-2 artwork. Every recipe below ends in a bypass.

---

## 0. What the show actually has (grep of `prismfest26-show/`, `concert-visuals-research/`)

| Fact | Source |
|---|---|
| IMAG = live artist camera on the outer fronts **L1 + R1** (portrait 2:5, 20x50 ft, 1152x2880 at 75% / 1536x3840 native), cropped 2:5; states LIVE-LOOP (IMAG in artist frame), TALK (IMAG on, low motion, nothing flashing), TAKEOVER (IMAG off), HOST (IMAG of host), OUTRO (IMAG wide or artwork) | `prismfest26-show/STAGE.md` "Screen roles"; `RUNTIME.md` state table lines ~83-89, spec table §7 |
| Resolume layers: 3 IMAG-L, 4 IMAG-R, 5 FRAME (C-2 IMAG frames, alpha), **6 FX = "TouchDesigner via Syphon + live FX", "reactive loss -> base loop keeps running"**; camera loss -> C-2 artwork | `RUNTIME.md` §8 table |
| SAFE HOLD state for "lost camera, failed clip"; hold and blackout always one action away | `RUNTIME.md` state 12; `STAGE.md` |
| **Camera plan is open**: "how many cameras, clean feeds to FOH, latency (needed for IMAG on L1/R1)". Organiser provides cameras and clean feeds; cameras themselves are not in Jazib's scope, "live camera FX" is | `RUNTIME.md` open items; `SHOW.md` "Jazib's engagement" |
| Commissioning includes "test cameras/TD/redundancy" on Fri 23 Oct; fps 30, Rec.709 pending (RFI08: capture I/O, camera latency) | `RUNTIME.md` timeline; `STAGE.md` |
| Camera-FX idea bank: duotone IMAG (Plum/Orchid + triangle frame corner), spectrum-split IMAG on drops (StageLab `JZB_RGBSplit`), IMAG background removal/duotone as branded IMAG, host IMAG cut-out over a Karachi landmark collage (ref 123), crayon world with IMAG in drawn frames (ref 121), 3 flashes/s limit applies | `concert-visuals-research/branded-look-ideas.md` B4 #16-17, #31-32; `pop-concert-styles.md` rows 121/123; `host-states.md`; `README.md` §4 |
| Flash rule: sequence not allowed if more than 3 flashes in any second **and** over 25% of the screen; saturated red flashing singled out | `concert-visuals-research/README.md` §4 |
| Existing live-input path in the viewer: Syphon/NDI -> `live_bridge.py`; Resolume NDI "Arena - Composition" 4538x1744 plays at ~27-28 fps; NDI latency **not measured** | `production/SYSTEM.md` rows "Live input" and notes |
| Stage-wide **venue is outdoor at night** (cricket ground, floodlights, haze unknown) | `STATUS.md` viewer notes; relevant to every vision model below |

No document names a camera model, a crowd cam, a PTZ or a capture card. The only thing known: there will be IMAG cameras for L1/R1, delivered as clean feeds to FOH.

### Prior art in `td-port/` (separate project; nothing imported; read READMEs only)
- `td-port/camera_bridge/`: **`jzb_camera_bridge`**, a native arm64 Objective-C++ helper (Core ML + Vision) that TD's Python talks to over a Unix-domain socket. Requests: kind 1 depth (Depth Anything V2 Small, Apache-2.0), kind 2/3 person segmentation (Fast/Balanced), kind 4 faces (Vision face rectangles), kind 9 info.
  Frames travel by TD Python only (no Syphon): one request in flight, newest frame wins, frame id echoed. Helper is arm64-only because a universal helper spawned from Rosetta TD would itself run translated (td-port probe: `x86_64 translated=1` vs `arm64 translated=0`).
  **Measured outside TD** (client = TD 2's own Python 3.11 x86_64 run outside TD, paced 60 fps loop; td-port README, 14-15 Oct 2026): depth round trip 66.7 ms median (compute 53.9 ms, ~15 maps/s); Fast mask 33.3 ms (compute 19.7 ms, ~32/s); Balanced 33.4/50.2 ms; faces 17-70 ms per detection at 960x540; model load 8.25 s the first ever time, ~70 ms after.
  **Not established: anything inside TD** (texture exchange, Script TOP upload cost, crashes). Its own findings: Vision keys people at medium/close range; "a dense crowd keys as one blob and small far people are missed".
- `td-port/person_key/` (6 looks: cut-out, silhouette, neon rim, person echo, per-person colour, shadow), `depth_fx/` (fog/grade/key by depth), `tracker/` (face wall; "it finds faces; it does not recognise anyone", MATCH % is decorative, showing audience faces is the production's call),
  `crowd_energy/` (how much the picture moves -> 0..1 level + CHOP output; "movement only: no person detection"), `flow_fx/` (GPU block matching on a quarter-size grey copy: Smear/Particles/Streaks/Flow Color). All written offline; per `td-port/STATUS.md` ("Not run at all ... camera set (fixtures only, no live camera): camera_bridge gate first, then depth_fx, person_key, tracker, crowd_energy, flow_fx") **none has run in TD**.
  These are ports of StageLab FFGL plugins; their value here is the designs (one-in-flight, frame ids, pass-through when the helper is missing), not the code.

---

## 1. Camera inputs in 2025.31550 on this Mac

### 1.1 Op classes (probed `dir(td)` + creation in a scratch COMP, deleted)
| Op | Result on this Mac | Evidence |
|---|---|---|
| `videodeviceinTOP` | class exists; **not created** (would open a device) | `dir(td)`; guardrail |
| `videodevicesDAT` | creates, no errors, `driver` menu = directshow, mediafoundation, datapath, blackmagic, alliedvisiongige, idsueye, idspeak, pointgreyflycapture, flirspinnaker, **avfoundation (default)**, bluefish444, aja, ximea, deltacast. Table: `input avfoundation FaceTime HD Camera V1\|\|\|47B4...` (+ same as `output`). Enumeration made no permission prompt | probed `d.par.driver.menuNames`, `d.text` |
| `ndiinTOP`, `ndioutTOP`, `syphonspoutinTOP`, `syphonspoutoutTOP`, `videostreaminTOP` (RTSP etc.), `renderstreaminTOP` | classes exist; **not created** (network/Syphon). `renderstreaminTOP` and `st2110inTOP` reported "not supported on this operating system" when created | probed |
| `webrenderTOP` | creates; `active` default False; `url` default `https://www.derivative.ca`; pars incl. `mediastream` ("Enable Media Stream"), `audio`, `maxrenderrate` (default 30), `numbuffers` (5), `dpiscale` (2.0), `sharedtexture`, `userdir`, `options`, `autorestart` | probed pars of `/project1/_research_probe1/wr` (destroyed) |
| `blobtrackTOP` / `blobtrackCHOP` | create; only error is "Not enough sources specified" (no input) -> works on Mac (in-build doc: OpenCV-based; SimpleBlobDetector + Background Subtraction modes; unlimited blobs in Pro) | probed + in-build `Blob_Track_TOP.htm` |
| `orbbecTOP`, `realsenseTOP`, `oakdeviceCHOP`, `ousterTOP` | create without an OS error (Oak: warning "Unrecognized Sensor ID", Ouster: "Could not connect with the device"). `leapmotionTOP`: "Leap Motion library and/or driver could not be found". | probed |
| `kinectTOP`, `kinectazureTOP`, `zedTOP`, `bodytrackCHOP`, `facetrackCHOP`, `facetrackSOP`, `opticalflowTOP`, `nvidiabackgroundTOP`, `nvidiaupscalerTOP` | **"This node is not supported on this operating system."** | probed (`o.errors()` after `cook(force=True)`) |
| `nvidiartxvideoTOP` | creates ("Not enough sources"); it is NVIDIA RTX per the release notes (agent A); do not rely on it | probed |
| `cplusplusTOP` | exists (custom plugin route; must be x86_64 under Rosetta per td-port/LEARNINGS) | probed |

Caution already in T-14/A: `dir(td)` lists Windows-only classes; "creates" is not "works". Only the probes above (creation + errors) are evidence of OS support.

### 1.2 Video Device In TOP (in-build doc `Video_Device_In_TOP.htm`, matches 31550)
- `driver` menu includes **AVFoundation (macOS)**, Blackmagic, AJA (both Windows and macOS with timecode, 12-bit), Magewell HDMI-to-USB3 "highly recommended, no drivers, plug-and-play". Deltacast/Bluefish: Windows only.
- Pars: `active`, `driver`, `device`, `signalformat` (resolution, rate, progressive/interlaced; "when using an interlaced format, the rate refers to fields per second"), `deinterlace`, `outputresolution`, `transfermode` (Automatic/Pre-Upload/On-Demand; "On-Demand, Sync to Frame Input" **AJA only**), `memorymode` (Pinned/Regular), `inputpixelformat` (8/10/12/16-bit, "some capture devices support more than 8-bit"), `inputcolorspace` (Rec.709 etc.), `syncinputs` (Blackmagic, DataPath, Deltacast, Bluefish; needs genlock).
- Info CHOP counters: `capture_fps`, `signal_fps`, `frames_dropped`, `frames_repeated` (a 30 Hz signal at 60 fps repeats frames by design). Doc: "If a device is listed but gives no video, make sure no other application is using the device" -> **a capture device can usually be opened by one app at a time** (if Arena owns the card, TD cannot; use Syphon/NDI from Arena instead) - single-owner behaviour for specific cards is **unverified**.
- Bundled vendor libs (bundle `Contents/Frameworks`): `libAJA.dylib`, `libajantv2.17.0.0.834.dylib`, `libBM.dylib`, `libndi.dylib` (+ `libndi_licenses.txt`), `Syphon.framework`, `librealsense2.2.56`, `libOrbbecSDK.1.10`, `libdepthai-core`. Whether a Blackmagic/AJA card also needs the vendor's own driver installed on the Mac is **unverified**.
- Camera permission: Info.plist `NSCameraUsageDescription` = "Required for Video Device In TOP." (bundle). Doc is silent on prompts. Forum: bug report "Unable to trigger Camera Permissions on macOS" (TD 2025.32280 **arm64**, M1 MacBook, macOS 15.6.1, posted 22 Jan 2026): FaceTime camera listed but black/error, TD never appears under Privacy & Security > Camera, reinstall and `tccutil` resets didn't help, no Derivative reply captured
  ([forum](https://forum.derivative.ca/t/bug-report-unable-to-trigger-camera-permissions-on-macos/927476)). Older anecdote (2021): launching TD first/restarting helps ([forum](https://forum.derivative.ca/t/video-device-in-webcam-doesnt-work/12208?page=2)). **Nothing found about Rosetta specifically.**
  Expected behaviour for this app (unverified): first `active` on the Video Device In (or the MediaPipe page's `getUserMedia`) triggers one macOS prompt for "TouchDesigner 2"; a hung modal can freeze TD until answered, so do it with the user at the keyboard, not through the MCP.
- NDI webcam: the doc's example device entry is "NDI Webcam Video 1" (NDI Tools' virtual webcam appears as an AVFoundation device; not installed/checked here).
- OBS.app is installed (`/Applications/OBS.app`). Its Virtual Camera is how the MediaPipe README feeds Syphon video into the plugin on Mac (below); whether the virtual-camera extension is activated on this Mac is **unverified** (probed device list shows only the FaceTime camera, so it is not active now).

### 1.3 NDI In TOP, Syphon Spout In TOP
- NDI In TOP (in-build/online doc): `active`, `name` (source), `extraips`, `bandwidth` (high/low), `hwdecode` (**NDI|HX only**; native NDI is software), `inputpixelformat` (native/8-bit), color-space pars, `audiobuflen`. Doc silent on receive modes, low-latency and macOS. "Software NDI solutions can only send native NDI, not HX."
  Latency: NDI's own white paper: "technical latency of 16 video scan lines ... in practice most implementations would be one field", hardware within 8 scan lines
  ([docs.ndi.video](https://docs.ndi.video/all/getting-started/white-paper/encoding-and-decoding)); HX figures are third-party and conflict (under 100 ms to 300 ms; 1-3 frames). **No measured NDI latency for this setup exists** (SYSTEM.md says the same).
- Syphon Spout In TOP: `sendername`; same computer only (shared memory) ([doc](https://docs.derivative.ca/Syphon_Spout_In_TOP)). Syphon is 8-bit RGBA per agent A's reading of the Out doc. Resolume's own streaming guide says Syphon has lower latency than NDI on Mac
  ([resolume.com/support/en/Streaming](https://resolume.com/support/en/Streaming), vendor statement; no number).
- Rule of the brief: neither was created or started here.

### 1.4 Resolution, fps, latency (what is known)
- Camera -> TD: no latency figure for AVFoundation, capture cards or NDI exists in this build's docs; any number must be measured with the real feed (a clapper/LED test: send a counter, compare camera-to-wall). `Info CHOP` `signal_fps`/`capture_fps` give rates, not latency.
- Web Render TOP default `maxrenderrate` = 30 (probed). The MediaPipe component sets its own page; README: "`totalInToOutDelay` ... in TouchDesigner 2022.33910 this is at least 3 frames for the web browser component" (old build; **no figure for 2025.31550**).
- Frame size reality for IMAG: a 1080p camera cropped to 2:5 is 432x1080 px (1080 x 2/5); the face is 1152x2880 (75%), so the crop is upscaled **2.67x** (arithmetic from `RUNTIME.md` face sizes). At 9984x3840-native L1/R1 (1536x3840) it is 3.56x. A 4K camera would give 864x2160 (1.33x/1.78x). Camera resolution/sensor matters more than any TD effect.

---

## 2. MediaPipe in TouchDesigner: torinmb/mediapipe-touchdesigner

Links: repo [github.com/torinmb/mediapipe-touchdesigner](https://github.com/torinmb/mediapipe-touchdesigner); releases [/releases](https://github.com/torinmb/mediapipe-touchdesigner/releases); latest tag [v0.6.0](https://github.com/torinmb/mediapipe-touchdesigner/releases/tag/v0.6.0).
All facts below from the repo README, release notes and GitHub API read on 16 Oct 2026 unless marked.

### 2.1 Release and licence
| | |
|---|---|
| Latest | **v0.6.0**, published **2026-10-14T19:30:49Z**, asset `release.zip` (187,899,060 bytes). Note: "tested on TD 2023.11880 and TD 2025.xxxxx. It runs on both Mac + PC" - the "xxxxx" is literal placeholder text, so v0.6.0's tested 2025 build is **not stated** |
| Before it | v0.5.3 (2026-08-10; tested "TD 2023.11880 and TD 2025.33070"), **v0.5.2 (2025-11-06; tested "TD 2023.11880 and TD 2025.31500"; fixed "bug in the new 2025 build of TD, causing the MediaPipe's video to scale because of the new DPI parameter on the web browser")**, v0.5.1 (2025-06-15), v0.5.0 (2025-01-21) |
| Licence | **MIT** (GitHub API `license.spdx_id`; README) |
| Repo state | 2,818 stars, 59 open issues, last push 2026-10-14 (GitHub API) |
| `@mediapipe/tasks-vision` | 1.0.1 (v0.6.0 notes "Bump versions"; repo `package.json` still says 0.5.2 / tasks-vision 1.0.1) |
| Size | MediaPipe.tox "very large (500MB+)" -> must enable **External .tox** when dragging in (`external_tox.md`). Install = unzip `release.zip`, open `MediaPipe TouchDesigner.toe` (README) |
| Installing on this Mac | **not done** (guardrail); would need the user's go-ahead (download ~188 MB) |

Closest-to-our-build evidence: **v0.5.2 was tested on 2025.31500**, 50 builds before our 31550 (same release family as POPs). Issue #170 (Mar 2026): after updating TD "to make use of the new POP operators" a user got "Webcam failed to start", plugin maintainer pointed at the latest release; the user still got it with the Nov-2025 release (Logitech Brio on probable Windows; OBS virtual camera worked)
([issue #170](https://github.com/torinmb/mediapipe-touchdesigner/issues/170)). This is the exact family of failures to expect.

### 2.2 How it works (README "How do the plugins work?"; source `src/main.js`, `src/*.js`)
1. A **Web Server DAT** inside `MediaPipe.tox` serves an embedded web app and a WebSocket (plus a separate `/segmentation` socket since v0.6.0). Everything is stored in TD's virtual file system, so no internet is needed once loaded.
2. A **Web Render TOP** (embedded Chromium; our build bundles CEF framework version **132.3.1.0**, x86_64, bundle `Info.plist`; the Info DAT would give the Chromium version) loads the page.
3. The page opens the camera itself with `navigator.mediaDevices.enumerateDevices()` / `getUserMedia` (`src/main.js`, `src/state.js`), runs MediaPipe Tasks Vision (WASM) with **`delegate: "GPU"`** (WebGL) in `runningMode: "VIDEO"` (`faceLandmarks.js`, `handGestures.js`, `poseTracking.js`), draws overlays, and sends JSON results back over the WebSocket.
   The TD side needs the Web Render TOP's **`mediastream` ("Enable Media Stream": "Allows the web render instance to use the mic and the camera")** on (probed: exists, default False).
4. JSON decoders (`face_tracking.tox`, `hand_tracking.tox`, ...) turn results into CHOPs/DATs/SOPs.
5. Segmentation (v0.6.0): runs in a Web Worker, masks zlib-compressed and sent as binary to the Web Server DAT, copied into a `seg_data` Script TOP; mask matched to the exact video frame via a frame marker pixel and a `segCacheOffset` for a Cache TOP.

### 2.3 Models and outputs
| Task | Model files in repo | Output in TD |
|---|---|---|
| Face landmarks (up to ~5 faces; blendshapes; transformation matrices) | `face_landmarker.task` | CHOP (per-face samples since v0.5.0), SOP mesh, DAT; OpenPose-style points, UV map; `face_filter_example`, `face_mapping_example`, `face_3d_object_example` |
| Face detector | `blaze_face_short_range`, `blaze_face_full_range` (v0.6.0 adds `Fdmodeltype = fullrange` "for faces further from the camera") | boxes |
| Hands + gestures | `gesture_recognizer.task`, `hand_landmarker.task` (v0.6.0: only the gesture model runs; any number of hands; `Lock Handedness` for h1/h2 left/right) | one merged hand SOP (breaking change), CHOP channels `h1..hN`, gesture names, pair distances `h1h2:distance` |
| Pose | `pose_landmarker_lite/full/heavy` | CHOP (`p0:`/`p1:` prefixes, two poses), SOP/OpenPose converter |
| Object detection | `efficientdet_lite0/lite2`, `ssd_mobilenet_v2` | boxes + labels (Circle/Line render modes) |
| Image segmentation | `selfie_segmenter` (square, landscape), `selfie_multiclass_256x256`, `hair_segmenter`, `deeplab_v3`; "MultiCam" model for "most accurate web-cam cutout" | `seg_data` Script TOP. Native mask sizes: 256x256 selfie/multiclass, 256x144 landscape, 512x512 hair, 257x257 DeepLab. "Resize the TOP after `seg_data`" |
| Image classification / embedding | `efficientnet_lite0/2`, `mobilenet_v3` | DAT. README: supports "all MediaPipe vision models except Interactive Segmentation and Image Embedding" (embedder code exists) |
| Timing | | `timers` CHOP: `detectTime`, `drawTime`, `sourceFrameRate`, `realTimeRatio`, `totalInToOutDelay`, `isRealTime`, `seg*` fields |

Camera options: any webcam in the drop-down; input "limited to 720p" in the README, but v0.5.2 added a resolution parameter for >720p; v0.6.0 enforces `Target Frame Rate` on the webcam. **Feeding a TOP** (e.g. a capture card or Syphon): Windows = Spout + SpoutCam; **Mac = Syphon -> OBS -> OBS Virtual Camera -> select it in the plugin** ("not the most elegant solution, but it works").
So on Mac a non-webcam source costs an extra app and a virtual camera hop.

### 2.4 Known issues relevant to us (GitHub issues, read 16 Oct 2026)
- Camera not found/black on Mac: #140 (open, Jun 2025, "TD 2023 on Mac ... error -108"), #131 (Apr 2025, closed: "camera works in Video Device In but not in MediaPipe"), #165 (open, Feb 2026), #158 (closed Jan 2026, M2 MacBook Air: "download the release.zip, not master"), #170 (above). Common fix given: use `release.zip`, not the source. No fix for the -108 case is posted.
- #168 (Mar 2026, TD **2025.31310**, MacBook, FaceTime camera): face-tracking component shows "1 network with errors inside"; a reply suggests a wiring workaround (the v0.5.3 notes add auto-connect on drag).
- #180 (open, 8 Sep 2026, TD 2025.33070 + MediaPipe 0.5.3): face-tracking torus does not appear unless "Match Transformation Matrices" is disabled. Only 1 comment; not yet answered in the page.
- #162 plugin hangs at "Loading" if TD is started with `sudo` (note Orbbec cameras need `sudo` on Mac, so avoid combining them).
- v0.6.0 notes: fixed "results slowing to ~1 fps after a while", masks missing when many models run, `Fdmodeltype` ignored. Results "no longer queue up when TD falls behind. Stale frames are dropped (max 3 in flight)."
- README: "MediaPipe tasks are very CPU and GPU intensive, so turn off any that you aren't using."
- **No issue or note about Rosetta/Intel-TD or an fps number on Apple silicon** was found (web searches, 16 Oct 2026). The plugin's `timers` CHOP is the measurement tool once it is installed.
- Risk specific to this build (unverified): Web Render TOP `dpiscale` default is 2.0 here (probed); v0.5.2 fixed a video-scaling bug from the "new DPI parameter". Whether v0.6.0 still sets it is not checked.

### 2.5 Fit for PF26
Strengths: one component gives hands, gestures, pose, faces, segmentation; MIT; no installs inside macOS besides the TD app; data comes out as CHOPs (control signals) which suits "triggers" and "level" use.
Costs/risks: ~188 MB download, 500 MB+ tox, extra Chromium process load on a laptop that also runs the show; camera permission uncertainty; GPU WebGL inside CEF under Rosetta untested; model inputs small (selfie mask 256x256) so a mask on a 2880-px-tall face needs soft edges (the mask is "a look", not a matte).

---

## 3. Other routes

### 3.1 TD built-ins on this Mac (probed table in §1.1)
- **Body Track CHOP** (NVIDIA Maxine AR SDK, RTX 20-50 series, Windows only), **Face Track CHOP/SOP** (same), **NVIDIA Background TOP** (Maxine green-screen, RTX 20/30/40, Windows only), **Optical Flow TOP** (Windows only, NVIDIA 3000+): in-build docs `Body_Track_CHOP.htm`, `Face_Track_CHOP.htm`, `NVIDIA_Background_TOP.htm`, `Optical_Flow_TOP.htm`; all four also fail on creation here. **Not available on this Mac.**
- Kinect (v1/v2), Kinect Azure, ZED: not supported on this OS (probed).
- **Orbbec TOP**: supported on macOS but "connecting to Orbbec cameras on Mac OS systems requires root privileges" (launch TD with `sudo`) (in-build `Orbbec_TOP.htm`; collides with the plugin's #162). Outputs colour, depth (32-bit float metres), IR, point cloud, IMU. Skeleton tracking for Femto Mega/Bolt. No camera here to test.
- **RealSense TOP/CHOP**, **OAK** (`depthai` bundled; OAK Device CHOP runs custom DepthAI pipelines, "connect devices before starting TouchDesigner"): create fine; no hardware here, unverified. Not relevant to an outdoor show.
- **Blob Track TOP/CHOP**: OpenCV, works (SimpleBlobDetector, Background Subtraction); unlimited blobs in Pro. **Palette `opticalFlow`** (`tfs/Samples/Palette/Tools/opticalFlow.tox` exists in the bundle): GPU network, pars Force/Offset/Lambda/Threshold/Inverse X/Y; the docs say the TOP is "NVIDIA-only" and recommend it, but the palette itself is a plain component (Mac behaviour **unverified**; not loaded, per no-build rule).

### 3.2 Python inside TD (probed)
- `import cv2` -> `4.11.0`, `/Applications/TouchDesigner 2.app/.../site-packages/cv2/__init__.py`, binary **x86_64**; built with TBB and OpenCL, AVFoundation YES (camera capture by OpenCV would open a device - not touched). Present: `cv2.ximgproc`, `bgsegm` (MOG/GMG), `optflow` (DIS etc.), `dnn` (`readNetFromONNX`, CPU/OpenCL/Vulkan targets, **no CoreML target**), `face`, `aruco`, `dnn_superres`, `FaceDetectorYN`, `CascadeClassifier`, `HOGDescriptor`, Farneback, `BackgroundSubtractorMOG2/KNN`. `tracking` False.
- Also in TD's site-packages (bundle): `depthai` 2.30, `numpy 2.1.2`, `requests`, `pygdtf`, `pymvr`, `attrs`, `yaml`, `pip`. Missing (probed `importlib.util.find_spec`): `onnxruntime`, `mediapipe`, `torch`, `coremltools`, `scipy`, `PIL`, `objc`/`Vision`, `pythonosc`, `tensorflow`.
- Installing ML wheels into Rosetta TD's Python: PyPI JSON (16 Oct 2026): `mediapipe 1.1.1` has only `macosx_11_0_arm64`; the newest wheel with an x86_64/universal2 macOS build for cp311 is `mediapipe 0.10.21` (Feb 2025; requires `numpy<2`, `protobuf<5`, `jax`, `matplotlib`, `opencv-contrib-python`) - it would fight TD's NumPy 2.1.2.
  `onnxruntime 1.31.0` is arm64-only on macOS; newest cp311 x86_64 is `1.23.2`. Both would run **translated CPU** in TD's process, and td-port measured TD's Python ~2x slower than native. **Not recommended and not installed**; the helper-process route avoids all of it.
- Script TOP: `copyNumpyArray` (3 or 4 channel), "How the NumPy array is generated is entirely up to the script writer, custom code, OpenCV, etc." (in-build `Script_TOP.htm`).

### 3.3 External native helpers (arm64) and apps
- **td-port `jzb_camera_bridge`** (above): Apple Vision person mask/faces, Core ML Depth Anything V2. The only route here with local measurements (outside TD).
- **CoreML Syphon Bridge** (Aristides.Lab, posted 22 Apr 2026): standalone macOS app, any `.mlmodel`; Syphon in/out; bundled Depth Anything V2, DETR ResNet50 segmentation, MiDaS, 16 tested models; claims "40+ FPS" depth (no hardware/resolution stated); macOS 14+, Apple silicon, distributed via Patreon, **licence not stated**
  ([derivative.ca community post](https://derivative.ca/community-post/tutorial/touchdesigner-coreml-syphon-bridge/74429)). Third-party, not audited; guardrail: nothing downloaded.
- **TDLidar** (iOS app, Aristides Lintzeris, posted 2 May 2026): iPhone TrueDepth/LiDAR -> **NDI** (depth, RGB, side-by-side) + **OSC** (`/tdlidar/body/*` 17 keypoints, `/face/*` 52 ARKit blendshapes + 4x4 transform, `/hand/*` 21 landmarks per hand, motion 50 Hz, audio FFT, speech). iOS 18.6+, same Wi-Fi, "50-80 ms end-to-end on Wi-Fi 5, ~30 ms on Wi-Fi 6" (author's estimate), depth 30 fps, free on App Store, no licence stated
  ([derivative.ca](https://derivative.ca/community-post/tdlidar-%E2%80%94-turn-your-iphone-realtime-depth-tracking-and-audio-sensor-touchdesigner)). Wi-Fi at a festival FOH is a risk (multicast/Bonjour for NDI discovery). Unverified; not installed.
- **MediaPipe in native Python sending OSC**: `mediapipe` wheels exist for macOS arm64 (PyPI); a separate venv with native Python, `python-osc` and OpenCV could read a camera/NDI/Syphon feed and send OSC to TD's OSC In CHOP (class exists, probed). This duplicates the plugin's job with more control over latency/threads and removes Chromium. It is a build, so only a candidate; **not tested**.
- OBS (installed) as a hub: Syphon Client / NDI source -> Virtual Camera, used by the plugin README on Mac.
- OSC/NDI/Syphon inputs and `oscinCHOP`, `oscinDAT`, `ndiinTOP` exist as classes (probed). Zig Sim and Record3D were not researched (searches returned only TDLidar); both are **unverified**.

### 3.4 Depth, background removal, optical flow summary
| Need | Built-in here? | Working route in this build | Cost evidence |
|---|---|---|---|
| Optical flow / motion field | Optical Flow TOP: no (Windows/NVIDIA) | Script TOP + OpenCV Farneback (verified, §5.2); or GLSL block matching (td-port `flow_fx`, unrun in TD); or `cv2.optflow.DIS` (present, untested) | probed 42 ms/cook |
| Person mask | NVIDIA Background TOP: no | MediaPipe selfie segmentation (plugin); Apple Vision via `jzb_camera_bridge`; classic background subtraction (`BackgroundSubtractorMOG2`, Blob Track TOP) for a **fixed camera** | Vision Fast mask 33 ms round trip outside TD |
| Pose / skeleton | Body Track CHOP: no | MediaPipe pose (plugin); TDLidar ARKit body over OSC; Orbbec skeleton (hardware) | unmeasured |
| Hands / gestures | Leap Motion needs its driver | MediaPipe gesture recognizer (plugin) | unmeasured |
| Faces | Face Track: no | MediaPipe face landmarks; Vision faces via helper (17-70 ms) | helper numbers outside TD |
| Depth from RGB | none | Depth Anything V2 via helper (66.7 ms round trip, ~15/s outside TD) or CoreML Syphon Bridge (vendor claim) | td-port README |
| Colour/segment | Chroma Key / RGB Key TOP (not probed) | existing | n/a |

---

## 4. PRISMFEST'26 uses, risks, what needs the venue feed

### 4.1 Ideas mapped to routes
| Use (source) | Technique | Needs the venue feed? | Prototype on the Mac webcam? |
|---|---|---|---|
| **IMAG treatment on L1/R1**: duotone Plum/Orchid, thin triangle corner frame, spectrum-split on drops (`branded-look-ideas.md` #16-17) | colour grade + RGB offset in TD (no ML); or the same in Resolume | Yes for the real look and crop; the grade logic can be built on any footage | Yes (FaceTime camera or a clip) |
| **Portrait 2:5 crop and framing** of the camera | Crop/Fit TOP; face-aware crop via face detector | Yes - framing, headroom, camera angle are venue facts | Partly |
| **Host cut-out over a landmark collage** (ref 123; host states T1/T4) | person segmentation (MediaPipe selfie / Vision mask) -> Matte over collage | Yes (host on stage, stage light) | Yes for the pipeline, no for edge quality at night |
| **Silhouette / PRISM spectrum through the artist** (`prism-brand`, `branded-look-ideas.md` "IMAG background removal") | person mask -> gradient/spectrum fill, rim light, echo (td-port `person_key` looks) | Yes | Yes |
| **Hand/gesture-triggered moments** | MediaPipe gesture recognizer -> CHOP -> Trigger CHOP with rate limit -> look switch/flare | Needs a camera that sees the performer's hands (close/medium shot); an artist cam on stage is the only plausible source | Yes (the pipeline) |
| **Crowd-cam / crowd energy** (`crowd_energy`): movement level drives glow/pulse | frame-difference or optical flow level (no person detection), 0..1 CHOP | Yes - needs a crowd camera, which is not in any document | Yes with a clip |
| **Face-tracked effects** (frames, brackets on faces) | MediaPipe face detector/landmarks or Vision faces | Yes | Yes. Audience faces on a wall: production/venue filming-notice call (td-port Tracker README) |
| **Camera-flicker / moire test** | none | Yes (RUNTIME flashing rule: "test moire and camera flicker") | no |

### 4.2 Risks and the rules that bite
- **Fail-safe.** RUNTIME layer 6: TD via Syphon; base loop keeps running; camera loss -> C-2 artwork. TD side needs: (a) a **Switch TOP** between live treatment and a clean fallback (pass-through camera or black), flipped by a watchdog on the result age (`timers.isRealTime`/frame counter for MediaPipe; `status` DAT for td-port's helper which "passes through the picture" when missing); (b) Web Render TOP `autorestart` (probed par "Restart if Process Died"); (c) never gate the camera layers on TD: IMAG-L/R live in Arena (layers 3-4), TD only adds an optional FX layer.
  If TD crashes, what a Syphon client in Arena shows (last frame or black/transparent) is **unverified**; test with Arena before relying on it (needs the user's go-ahead for Arena/Syphon operations).
- **Latency.** IMAG must lip-sync with the sound from the speakers. No figure for NDI or capture-card latency exists; MediaPipe adds web-render frames (>= 3 in an older build), Vision/Depth add 2-4 frames at 60 fps outside TD (td-port). Segmentation results arrive late: sync the picture with a Cache TOP offset (MediaPipe `segCacheOffset`; NVIDIA doc and td-port use the same idea), which delays the whole IMAG by the same frames. For lip-sync-critical IMAG, prefer **no ML on the IMAG path**: keep IMAG a plain camera layer in Arena and use ML only for decorative FX that can lag a few frames.
- **Lighting at night.** All models were trained on lit scenes; strobes, saturated LED wash, haze and backlight reduce landmark and mask quality (general, **unverified for this venue**). td-port: Vision "keys people at medium/close range ... small far people are missed ... a dense crowd keys as one blob". Auto-exposure and colour-flicker on LED backgrounds are the camera's problem (hence RUNTIME's "camera flicker" test).
  Mask quality must be judged on the real feed; a mask that wobbles is a flash source and breaks the <= 3 flashes/s, 25% rule: smooth masks (td-port PersonKey has Smoothing/Grow/Softness controls) and rate-limit gesture triggers to the flash rule.
- **Names intact.** Face/pose overlays must not cover or cut a name or logo; lower thirds belong to Resolume layer 7 and the IMAG frame/lower-third is separate from the TD effect. Labels on tracked faces (td-port Tracker) are decorative; do not use them for names.
- **Alpha.** An overlay with a person mask is an alpha layer; per the user's memory (overlay-alpha-premultiplied) alpha clips going to Resolume are premultiplied; Syphon from TD is 8-bit RGBA, so check Arena's blend with a test, not a straight composite.
- **Compute load on the show laptop.** TD, Arena and the web-render Chromium share one M1 Max. The show laptop's "redundant backup playback system" (SHOW.md) can't also carry these; budget CPU for decoding 7488x2880 DXV3. No combined measurement exists.
- **Privacy.** Segmentation/face detection of the audience: td-port says showing faces is "the production's call (venue filming notice)". Not decided.
- **Camera availability.** Unknown count/model; the plan says "clean feeds to FOH" (SDI most likely, **unverified**). SDI -> Mac needs a capture device: UVC SDI/HDMI USB capture (Magewell family is the doc's "no drivers, plug-and-play" example for HDMI-to-USB3), or Blackmagic/AJA hardware with the bundled drivers; or the organiser's NDI.
  Who owns the device matters: if Arena (layers 3-4) opens the capture card, TD receives the camera over Syphon/NDI from Arena (composition-level output only is confirmed: SYSTEM.md tested NDI "Arena - Composition"; a single-layer Syphon from Arena is **unverified**), which also adds the Arena crop/transform to what TD sees.

### 4.3 What needs the venue, what doesn't
- **Needs the venue feed (not before):** IMAG framing/crop, exposure under the LED wash, real mask quality, real latency chain, crowd cam, signal format (RFI08), and the capture hardware decision. Camera delivery likely SDI -> capture card (Mac) or NDI (organiser network); the plan is an open question in RUNTIME.
- **Can be built now on the Mac webcam or a clip:** colour grade/frame looks, the person-mask pipeline and its fail-safe, hand-gesture trigger logic with rate limiter, optical-flow/crowd-energy levels, face-detector crops, the Switch/watchdog scaffolding, Syphon-to-Arena alpha test, and a latency harness (counter overlay).
  (Using the FaceTime camera first needs the macOS permission test, §1.2.)

---

## 5. Recipes (op chains in 2025.31550; verified = built and cooked here)

Common: an op nothing views does not cook (T-02); `numpyArray()` right after a forced cook can return zeros (T-13) - read a frame or more later. All TOP/CHOP names are probed existing classes unless marked.

**R1 - IMAG duotone + frame + spectrum split (IMAG treatment). Unverified (device not opened).**
`Video Device In TOP` (driver `avfoundation`, device, `signalformat`) or `NDI In TOP`/`Syphon Spout In TOP` -> `Fit`/`Crop TOP` to 2:5 (1152x2880) -> `Level`/`Lookup TOP` (Plum->Orchid ramp) -> `Composite TOP` (frame corner PNG, premultiplied alpha) -> `Switch TOP` (input 1 = clean/black fallback) -> `Null TOP` -> `Syphon Spout Out TOP` -> Arena layer 6. RGB split: per-channel `Transform TOP` offsets or td-port's `JZB_RGBSplit` port (an unrun-in-this-session port). Keep within flash rules.
Verified part: `videodevicesDAT` enumerates the FaceTime camera; the rest of the ops exist. Not run: any device open, Syphon.

**R2 - Motion field / crowd energy with OpenCV Farneback in a Script TOP. VERIFIED (synthetic source).**
Chain probed: `Noise TOP` (640x360, static) -> `Transform TOP` (`tx` = `0.003*absTime.frame`, a known 1.92 px/frame at 640) -> `Null TOP` -> `Script TOP` (format `rgba32float`, 320x180, callbacks DAT) + `Execute DAT` (`onFrameEnd` -> `flow.cook(force=True)` pump).
Callback: `a = scriptOp.inputs[0].numpyArray(delayed=False)` -> grey uint8 -> `cv2.resize` to 320x180 -> `cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 2, 15, 2, 5, 1.1, 0)` -> out array R=flow x, G=flow y, B=magnitude, A=1 -> `scriptOp.copyNumpyArray(out)`; skip when `absTime.frame` equals the last processed frame (a second force-cook in the same frame produced identical frames and flow 0 until this guard).
**Result:** median flow x per cook = 0.96 px x frame gap at 320 wide: gap 4 -> 3.83, gap 3 -> 2.87, gap 7 -> 6.71 (expected 0.96/frame): correct magnitude. **Cost: median 42.5 ms, p95 109 ms per cook (80 cooks)**, which means the project cooked it every 3-7 TD frames (frame gap median 4 at 60 fps). Under Rosetta, other agents also using TD, so a conservative number, not a benchmark. Includes the GPU->CPU readback of a 640x360 float input and the 320x180 Farneback.
For a 0..1 "crowd energy" level: mean/percentile of magnitude after removing the median flow (camera pan) -> `Constant CHOP` + `Lag/Filter CHOP`; td-port `crowd_energy` is the designed version (unrun in TD). Faster alternatives (unverified): reduce to 160x90, or td-port's GLSL block matching.

**R3 - Person mask for silhouettes / spectrum through the artist. UNVERIFIED (two routes).**
(A) MediaPipe plugin: `MediaPipe.tox` (External .tox on) with `Detectsegments` on, model `Smodeltype` selfie / multiclass; `seg_data` Script TOP (256x256 float mask) -> `Resolution TOP` (resize) -> `Blur TOP` (soft edge) ; camera -> `Cache TOP` with `segCacheOffset` so the mask matches its frame -> `Matte TOP`/`Multiply` against a `PRISM spectrum` TOP (gradient from brand tokens) -> `Over` the base. Needs: plugin download (approval), camera permission test.
(B) td-port helper: `Resolution TOP` (SegReadSize) -> frame-end `numpyArray` -> Unix socket request kind 2/3 -> mask answer (float32, rows bottom-up) -> `Script TOP` `copyNumpyArray` -> same Matte chain. Needs `build/jzb_camera_bridge` (exists as a built artefact per td-port STATUS; not run here) and td-port's untested TD-side code.
(C) Fixed camera only: `BackgroundSubtractorMOG2` in a Script TOP on an empty-stage reference; no model, but only useful when the background is static and lit consistently (rare at a concert).

**R4 - Gesture trigger (hand up / open palm / etc.) -> look cue. UNVERIFIED.**
Plugin `hand_tracking.tox` (`h1` gesture channel names from the CHOP) -> `Select CHOP` -> `Logic CHOP` (gesture == name) -> `Trigger CHOP` (with minimum interval >= 0.33 s so no more than 3 events/s) -> `Count/Timer CHOP` -> a `Switch TOP` or an Arena clip trigger over OSC/MIDI (Arena operations need the user's go-ahead). Add a hold-time (gesture stable for N frames) to avoid false fires.

**R5 - Blob tracking / "where is the crowd moving". Partly verified (op creation).**
`Video/Syphon In -> Monochrome TOP -> Luma Level TOP -> Blob Track TOP` (`threshold`, `minblobsize`, `maxblobsize`, `maxmovedistance`, `reviveblobs`; `monosource`, `drawblobs`; probed pars) -> `Info DAT` of the TOP (blob IDs, coordinates, sizes; in-build doc) or `Blob Track CHOP` (`areaofinterest`, `outputvelocity`, `predicttype`; probed pars). Verified: both ops create on Mac and error only for "Not enough sources". Not verified: tracking quality on any footage.

**R6 - Phone sensors (iPhone TrueDepth/LiDAR) as a camera substitute. UNVERIFIED.**
`NDI In TOP` (Source Name from TDLidar) for depth/RGB + `OSC In CHOP`/`OSC In DAT` (probed class names) for `/tdlidar/face/*`, `/body/*`, `/hand/*` -> `Select CHOP` -> parameters. Requires an iPhone with TrueDepth/LiDAR and iOS 18.6, shared Wi-Fi with multicast; not tested; app unaudited (audit rule applies before any use).

Fail-safe wrapper for every recipe: `Switch TOP` (live vs clean), watchdog (frame/time of last result), Web Render `autorestart` where relevant, output `Null` -> `Syphon Spout Out TOP` -> Arena layer 6 only.

---

## Bugs hit / surprises (for the lead to log)
- **D1 - Another agent's probe COMP shares the name `_research_probe`.** My `create(baseCOMP, '_research_probe')` was renamed by TD to `_research_probe1` because `/project1/_research_probe` already existed with `m, gen, out, pump, gen_info, gen_pixel, gen_compute` (not mine). My first (disconnected) attempt did not run. Rule: use a per-agent probe name and never destroy a COMP you did not create; I destroyed only my own two (`_research_probe`, then `_research_probe1`); the other remains.
- **D2 - TD restarted mid-session** (pid 12186 -> 57376; `td_status` showed `td_connected: false` for ~1 minute at ~18:41 PKT). A shell session (not mine) ran `open -a "TouchDesigner 2.app" .../JazibTD_home.toe; sleep 45`. My prior probes had finished and destroyed their ops, so I don't think they caused it; cause not established. Project reopened as `JazibTD_home.1.toe`, `/jazib_mcp` reconnected on its own (consistent with T-07).
- **D3 - Two force-cooks in one frame feed a Script TOP identical input frames.** My pump (Execute DAT `onFrameEnd`) plus the cook triggered by `td_exec`/viewing gave zero flow/zero frame difference on the second call within a frame. Rule: guard the callback with the last-processed `absTime.frame`. (First reading, maxmag 0.03 px, looked like "flow not working"; it was this.)
- **D4 - `td_exec(frames=N)` waits until the cook of a heavy op finishes**, so "N frames" was in fact 171 TD frames in one probe (`frames` argument 10). Rule: read `absTime.frame` before and after.
- **D5 - Circle TOP `centerx` is not a 0-1 position in the default unit**: `0.3+0.2*sin` moved a radius-0.4 disc whose centroid sat at x=474 of 640; I abandoned the Circle for a Noise->Transform chain. Not investigated further (unit par not read).
- **D6 - Releases page of the plugin gives dates without years** in WebFetch; the GitHub API gave the real publish dates (v0.6.0 = 2026-10-14). The v0.6.0 note "TD 2025.xxxxx" is placeholder text in the release body.

---

## Open questions for the lead
1. **Camera permission test.** Do you want one supervised test (user at the Mac) of `Video Device In TOP` -> FaceTime camera in TD 2 (Rosetta) to see whether macOS 27 prompts and allows? It decides whether the MediaPipe plugin (camera inside Chromium) can work here at all. Everything camera-related waits on this.
2. **MediaPipe install go-ahead.** Download `v0.6.0` `release.zip` (188 MB; MIT) and test hands/segmentation/pose on the webcam, measuring with its `timers` CHOP? Or prefer the td-port native helper (Vision/Core ML, measured outside TD) as the first choice because it avoids Chromium/permission risk? Or both, compared on the same clip.
3. **Who opens the venue camera: Arena or TD?** RUNTIME has IMAG on Arena layers 3-4 with TD only on FX layer 6. Do you want TD to receive the camera (from Arena over Syphon/NDI) for IMAG treatments, or keep IMAG purely in Arena and use TD for non-IMAG FX (hand triggers, crowd energy, silhouettes)? The first adds a hop and latency on the lip-sync path.
4. **Venue camera plan:** how many cameras, SDI or NDI, which capture device (Magewell UVC / Blackmagic / AJA), 25/30/50 fps, who supplies a crowd cam? RFI08 is open in RUNTIME. Until answered, only Mac-webcam and recorded-clip prototyping is possible.
5. **Audience faces and silhouettes:** is face tracking of the audience allowed (td-port: "the production's call, venue filming notice")? Should crowd FX be limited to movement energy (no detection)?
6. **Scope:** MOU lists "live camera FX" in scope, cameras and clean feeds supplied by the organiser. Is a crowd-camera effect wanted at all, or only artist-cam IMAG treatments and host cut-out (ref 123)?
7. **Python route decision:** accept "no ML packages inside TD's Rosetta Python" (OpenCV only) and put every model in a separate arm64 process (td-port helper, a native MediaPipe-Python OSC sender, or the CoreML Syphon Bridge after audit)?
8. **Optical flow performance:** should a follow-up measure a GLSL block-matching flow (td-port `flow_fx` design) vs the 42 ms Script-TOP Farneback on 640x360 input, since Script TOP cost dropped the project's cook rate in my probe?
9. **OBS virtual camera:** do you want OBS's Virtual Camera extension activated for testing non-webcam sources through the MediaPipe plugin (the README's only Mac route for a Syphon/NDI/capture-card source)? It would add a camera device to the macOS list.
