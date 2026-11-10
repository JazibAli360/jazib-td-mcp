# BH - twozero rudiment "Face Tracking" (vankrav) and our clean-room build (research, 26 Oct 2026)

Target: TD 2025.31550, macOS Apple Silicon, TD = x86_64 under Rosetta, Vulkan/MoltenVK (T-46: multi-pass GLSL can tear, compute-mode is clean; T-18: Nvidia/Body/Face Track ops and Optical Flow TOP unsupported).
Notation: **page** = read from the page; **probed/bundle** = checked here on disk; **UNVERIFIED** = not established.
Nothing was run in TD, nothing installed, nothing signed in to. Clean-room: we study behaviour, not code.

## 1. What the original does

### 1.1 Sources and what could be read
| Source | Result |
|---|---|
| https://twozero.ai/rudiments/vankrav/face-tracking | 200, but a SvelteKit app: the body is client-rendered, so a plain fetch (WebFetch and curl) returns only the head. **Only the `<meta>` description + title + cover image were readable.** No parameters list, no download link, no price, no docs link in what was served |
| https://twozero.ai/rudiments (parent), `.../previz-stage` | 200, same shell (10 KB, no body text) |
| `cover.jpg` (1280x720, read) | A webcam portrait with a **green wireframe over the face**: eyebrows, eye outlines with a pupil dot each, nose bridge + nose base, outer lips + a mouth centre line, jawline/chin, a vertical centre line from forehead to chin. So the display is a landmark-wire overlay on the video |
| `robots.txt` | `/api/` is Disallow; we did not call it, and did not run the site's JS or look for a hidden download. Downloading a rudiment most likely needs a twozero account (UNVERIFIED); **not bypassed, no .tox obtained, nothing to `toeexpand`** |

Only hard facts about the original (page meta description, verbatim): "Real-time face tracking in TouchDesigner: **87 landmarks per face as named CHOP channels, eye and mouth openness, head roll, and face / eyes / mouth masks - Apple Vision on macOS, MediaPipe elsewhere**..." (text is cut with an ellipsis in the meta).

So, known: author vankrav; a twozero "rudiment" (small reusable TD component distributed through twozero, whose MCP is a closed `twozero.tox`, see `AF_peer_td_mcps.md`); outputs (a) CHOP with 87 named landmark channels per face, (b) eye and mouth openness values, (c) head roll, (d) three masks: face, eyes, mouth; backend: Apple Vision on Mac, MediaPipe on other OSes; an overlay view. Licence, price, TD build, parameter names, multi-face support, resolution and fps: **UNVERIFIED** (not on the readable part of the page). The "87 landmarks" count is the author's own scheme (Apple's Vision face landmarks give 76 points in the constellation-76 layout with pupils; how 87 is made up is UNVERIFIED), so our channel naming is our own and need not match.

Related prior notes: `D_camera_mediapipe.md` (camera routes, MediaPipe plugin, bridge, Farneback probe), `J_interactive_camera_effects.md` (J8 face-aware crop), `AV_macos_background_removal.md` (arm64-only Vision binary vs x86_64 TD; MIT source, rebuild x86_64), td-port `camera_bridge` (arm64 helper, faces kind 4 = rectangles only).

## 2. Clean-room build spec: `face_track` (self-contained COMP)

**Goal.** From a TOP (stored clip by default) produce, per frame and per face: a rectangle, roll, ~76 named landmark channels, eye/mouth openness, and face / eyes / mouth mask TOPs, plus a landmark-wire overlay. Names and layout are ours.

### 2.1 Backend decision (Mac, Rosetta, no Nvidia)
| Route | Landmarks | Mac/Rosetta fit | Verdict |
|---|---|---|---|
| **A. Apple Vision in the native arm64 helper** (extend td-port `jzb_camera_bridge`: add a request kind 5 = `VNDetectFaceLandmarksRequest`) | yes: 76 points (constellation 76), pupils, per-region contours, roll/yaw/pitch (revision dependent), confidence | Helper already proven inside TD 2 for mask/depth (T-27: median 27 ms round trip); faces kind exists as rectangles only (17-70 ms per detection at 960x540 standalone). Needs a new ObjC++ request + a rebuild of the helper: **new native code = the user's go-ahead** | **Primary** (same pattern as the person mask, no TD-bundled-Python limits) |
| B. MediaPipe via Torin's Web Render TOP plugin | 478 landmarks + 52 blendshapes | Camera permission blocker under Rosetta (D §0/§1); video comes from the web page's `getUserMedia`, not from our TOP, so **the stored clip cannot be fed**, unless the page is modified to read a file | Later option, FUTURE row; not testable on the clip |
| C. OpenCV in a Script TOP | `cv2` 4.11.0 is bundled (probed in T-19/D), but `FaceDetectorYN`/Facemark need ONNX/LBF model files we would have to download (not present in the bundle; `cv2/data` has no cascades; a `strings` check on the cv2 `.so` was inconclusive: the module layout is a package dir, so symbols were not confirmed) | CPU, x86_64, works without helper | **Fallback**: Haar/YuNet rectangle + a geometric landmark approximation only if a model is placed in the project with the user's OK (download = approval) |
| D. TD built-in Face Track CHOP/SOP | - | Not supported on this Mac (T-18, probed) | Out |

Python packages in TD's bundled Python (read-only listing of site-packages): cv2, numpy 2.1.2, depthai, attrs, jsonschema, PyYAML, certifi... **no mediapipe, onnxruntime, torch, pyobjc, Vision binding**. So no Vision from TD's own Python: the helper is the only route.

### 2.2 Custom parameter pages (names: one capital then lowercase/digits)
Page `Input`: `Source` (menu: Clip/Top/Camera; default **Clip** = `media/webcam/webcam_ref_5s.mp4`; Camera only on the user's ask, set inactive after), `Clipfile`, `Maxfaces` (1-8, default 1), `Detectsize` (menu 480/640/960, default 640 wide), `Mirror` (toggle).
Page `Track`: `Active`, `Smooth` (0-1, one-euro-style smoothing strength), `Minconf` (0-1), `Holdframes` (keep last pose N frames on loss), `Rollunit` (menu deg/rad).
Page `Masks`: `Maskblur` (px), `Maskgrow` (px), `Eyeexpand`, `Mouthexpand`, `Maskres` (menu 256/512/full).
Page `Overlay`: `Showwire`, `Showboxes`, `Showids`, `Wirecolor` (rgb), `Wirewidth`, `Wireopacity`.
Page `Output`: `Facecount` (readonly), `Latency` (readonly ms), `Status` (readonly str), `Opencontrols` (pulse).
Page `Debug`: `Fakeface` (toggle: feed a synthetic landmark set so the whole downstream chain can be tested with the helper off).

### 2.3 In / Out (outputs carry only the output)
- In: `in_video` (In TOP). Optional `in_clip` (Movie File In TOP inside, used when `Source=Clip`).
- Out: `out_video` (Out TOP: input + wire overlay when `Showwire`), `out_face`, `out_eyes`, `out_mouth` (Out TOPs, 1-channel mask, R8/16f), `out_pts` (Out CHOP: per-face landmark channels, see 2.5), `out_ctl` (Out CHOP: face count, per-face openness, roll, rect, confidence). Out DAT `out_info` (status, latency, backend). No controls inside these Outs.

### 2.4 Network, stage by stage (each stage a titled box via `td_layout mode:"stages"`)
1. **Source** - `in_video`, `moviefileinTOP` (clip), `switchTOP` (Source), `flipTOP`/`transformTOP` (Mirror), `resolutionTOP`/fit to Detectsize, `nullTOP src`.
2. **Bridge** - frame pump: a `scriptTOP` (or `executeDAT` frame callback + `topto numpy`) hands the Detectsize BGRA frame to `lib/camera_bridge`-style client (one request in flight, newest frame wins, frame id echoed; pass-through when helper missing). Answer parsed into a Table DAT `faces_raw` and a float array in a Script DAT. Info CHOP/`out_info` shows ready/latency (cold start ~7 s per T-27: wait for ready).
3. **Landmarks to CHOP** - Script CHOP `pts` writes channels `f1_<region>_<n>x`, `..y` (regions: jaw, brow_l, brow_r, eye_l, eye_r, pupil_l, pupil_r, nose, nosecrest, lips_outer, lips_inner, median) in 0-1 image space, origin top-left, plus `f1_rect_x/y/w/h`, `f1_roll`, `f1_conf`. Faces beyond `Maxfaces` omitted; CHOP always carries `Maxfaces` x channels (zeros when absent, with `f<n>_present`).
4. **Smoothing / hold** - Python-side (pure function `smooth.py`, see 2.6) then `filterCHOP`/`lagCHOP` only for display channels; `Holdframes` keeps the last pose, `present` ramps down.
5. **Measures** - `out_ctl`: `eye_open_l/r` = eye height / eye width (from eye contour points), `mouth_open` = inner-lip gap / mouth width, `smile` = mouth-corner lift / width, `roll` = atan2 of the pupil line (fall back to rect roll), `scale` = rect w. All normalised 0-1 with calibratable `Eyeclosed/Eyeopen/Mouthmax` pars (rest values captured by a `Calibrate` pulse).
6. **Masks** - one **compute-mode** `glslTOP` (T-46: one pass, no multi-pass tearing): reads the landmark array through a small float TOP made by `choptoTOP` (channels packed into a 2-row texture), draws filled polygons: face (jaw + brow hull), eyes (eye contours, `Eyeexpand`), mouth (lips outer, `Mouthexpand`) as three outputs (three small passes or one 3-plane write; if the compute path cannot write 3 outputs, three single-pass compute TOPs reading the same point texture). Point-in-polygon by even-odd fan from the centroid over <= 16 points per region (sketch below). Then `blurTOP` (Maskblur), `levelTOP`/`mathTOP` for Maskgrow.
7. **Overlay** - draw the wire as GLSL compute (distance to segment over regions list; one pass, loop bound 16 per region) onto the video; `compositeTOP` over; `Showids` draws numbers with `textTOP` instanced only when on (cheap path off by default).
8. **Outputs** - `out_*` null->Out ops. **Controls** - `controls` panel (autoUI, `Pagescope` = slider page, `Pagetabs` off, `align verttb`, widget clones cut), `controls_window` opened by `Opencontrols` pulse, a small `status` Text with Facecount/Latency/Status.

GLSL sketch (mask stage, even-odd test; inside a compute `main()`):
```glsl
uniform int uN;            // points in region
// pts: sampler2D 1xN, rg = x,y in 0-1
bool inside(vec2 p){ bool c=false; for(int i=0,j=uN-1;i<uN;j=i++){
  vec2 a=texelFetch(pts,ivec2(i,0),0).rg, b=texelFetch(pts,ivec2(j,0),0).rg;
  if(((a.y>p.y)!=(b.y>p.y)) && (p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)) c=!c; } return c; }
```
Python sketch: `pts_from_answer(buf, faces)` -> dict region -> list[(x,y)]; `measures(pts)` -> eye/mouth/roll; `OneEuro(mincut, beta)` for `Smooth`.

### 2.5 Helper extension (the only native work)
Add `KIND_LANDMARKS = 5` to `td-port/camera_bridge` copy used by jazib-td (do **not** edit td-port: separate project; copy the helper source into `jazib-td-mcp/td/bridge/` under attribution, per the "nothing shared or imported" rule). Request = same 48-byte header; answer float32, per face: rect(4) roll yaw pitch conf, then N points (x,y), regions in a fixed table sent once in `info`. API: `VNDetectFaceLandmarksRequest` (revision 3 or latest) on the BGRA/luma buffer; `VNFaceLandmarkRegion2D.normalizedPoints` are relative to the face box, so convert to image space: `x = box.x + p.x*box.w`, `y = (1 - (box.y + p.y*box.h))` for top-left origin (UNVERIFIED which orientation flags it needs; the existing kind 4 test noted "rows bottom-up AND top-down" ambiguity - reuse that test).

### 2.6 Pure-Python logic testable offline (`test/test_face_track.py`, no TD)
- Region table + channel naming (`f1_eye_l_03x`) round trip; parse of the helper answer bytes (synthetic buffer) incl. 0 / 1 / 8 faces and truncated answers.
- Normalised-coordinate conversion (box-relative to image, bottom-up to top-down) with known points.
- `measures()` on hand-built landmark sets: open eye > closed eye, mouth open ratio, symmetric smile, roll of a rotated synthetic face = known angle +-0.5 deg.
- One-euro smoother: step response, no overshoot, `Holdframes` behaviour, `present` ramp.
- Even-odd point-in-polygon (python twin of the GLSL) on convex and concave regions; mask area ratio checks.
- `Maxfaces` ordering stability (sort by area, track ids by nearest-centre so ids do not swap).
- Pass-through when helper missing: Status text, outputs black but valid.
Run with `node --test`/pytest per the repo's convention; targeted tests only (memory rule).

### 2.7 Verifying live (clip first)
1. `Source=Clip` (`webcam_ref_5s.mp4`, 1920x1080 30 fps, face present per `D`/J notes: **check the clip actually shows a face on frame 0 with `td_screenshot` first**; if not, `Fakeface` verifies only the downstream).
2. `Status` = ready within ~8 s; `Latency` median < 60 ms at Detectsize 640 (target; td-port standalone 17-70 ms). Record the real number with `td_perf`.
3. Numbers: `out_ctl.facecount` = 1 on >= 95 % of the 150 frames; `f1_rect_w` between 0.1-0.6; landmark y order: eyes above nose above mouth above chin in every frame; `mouth_open` varies over the clip only if the person talks (compare with a frame grab); `roll` within +-15 deg for a normal pose.
4. Masks: `out_face` mean luminance equals polygon area ratio within 5 %; `out_eyes` and `out_mouth` strictly inside `out_face` (min(face, eyes) == eyes); mouth mask ratio grows when `mouth_open` grows.
5. Overlay: capture with `td_window_capture` and compare with the cover's look (brows, eyes+pupil, nose, lips, jaw, centre line).
6. Fail-safe: kill helper only by exact PID, check `present` ramps to 0 after `Holdframes`, Out TOPs stay valid, and nothing cooks errors (`td_errors`). Disconnected clip: black + Status text, no exception.
7. T-46 check: view the mask chain at full size after a steady cook; compute-mode must not tear; multi-pass chains verified twice.

### 2.8 Mac / 31550 caveats and fallbacks
- Everything Nvidia (Face Track CHOP/SOP, Body Track, Optical Flow TOP) is out (T-18). Our Face Track is a new COMP, not a wrapper.
- Helper must be arm64 only (translated child otherwise; td-port probe). First request is a ~7 s cold start (T-27).
- Camera: stored clip default; live camera permission under Rosetta is a known blocker (D); only on the user's request.
- GLSL: compute mode, one pass per output; loops bounded; no multi-pass chains.
- Fallback ladder: helper -> (user OK) YuNet/Haar in Script TOP, rectangle + ellipse mask only -> `Fakeface`. All keep the same Out ops, so looks never break.
- Install/native-build steps wait for the user's go-ahead (CLAUDE.md approval gates).

### 2.9 For docs/FUTURE.md (newer builds / newer routes)
| Feature | Needs | Note |
|---|---|---|
| MediaPipe 478 landmarks + 52 blendshapes route | Web Render camera permission on Mac / the plugin working on a newer build | second backend, same CHOP naming, blendshape channels `f1_bs_<name>` |
| Native TD Face Track CHOP/SOP wrapper | Windows + Nvidia only | wrap as a third backend on Windows builds only; gate on `app.osName` and class availability |
| Head yaw/pitch, 3D head pose, gaze | Vision revision with pose fields (macOS 14+ for some, UNVERIFIED) | extra channels `f1_yaw`, `f1_pitch` |
| Python Vision binding inside TD | a TD build with arm64 Python or pyobjc | removes the helper |

### 2.10 Related rudiments requested in the same message
The user also named timeline, zerror, screen-reprojection, db-meter (twozero) and previz-stage (vankrav); each gets its own research file. Note for the db meter: it takes audio from an In CHOP (our `AC_audio` COMP feeds the default input), and the default output stays the Mac speakers (td-audio-default-speaker rule).

## 3. Estimated build time
| Step | Time |
|---|---|
| Pure-Python module + offline tests (2.6) | 1.5 h |
| Helper `KIND_LANDMARKS` (ObjC++ copy + build + standalone test) - needs go-ahead | 2-3 h |
| TD client wiring, Bridge/CHOP stages, params | 2 h |
| Compute GLSL masks + overlay, Mac checks (T-46) | 2 h |
| Controls panel + window + layout stages, live verify on the clip | 1.5 h |
| Total | about 9-10 h of agent time; with parallel lanes (Python+tests, helper, GLSL) about 4-5 h wall clock |
