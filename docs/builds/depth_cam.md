# depth_cam - `/project1/lab/DC_depth_cam` (live-verified v1 in main, 26 Oct 2026, TD 2025.31550; T-92)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Depth from the camera: Core ML **Depth Anything V2 Small** (Apple's conversion, Apache-2.0) runs natively in our arm64
vision helper (`helpers/vision_bridge`, request kind 1); the COMP gets a depth TOP and four depth looks behind a
`Mode` par. Client pattern = face_track's: non-blocking, one request in flight, newest frame wins, frame id echoed,
pass-through when the helper or model is missing. Prior art: td-port `lib/depth_fx.py` (port of StageLab's
JZBV_DepthFX logic), whose range/field easing and request controller are copied here.

## Files
- `builders/depth_cam.py` - builder, `build(parent_path='/project1/lab', panel=True)`, via td_exec:
  `ns = dict(globals()); exec(open('<repo>/builders/depth_cam.py').read(), ns); ns['build']('/project1/lab')`
- `builders/depth_cam_logic.py` - pure logic (percentiles reference, range easer, field step, request controller with
  hold/pass-through, slice sweep, fake depth, info rows). Copied into the COMP's `depth_cam_logic` DAT.
- `builders/depth_cam_runtime.py` - TD glue (frame pump, helper lifecycle, Script TOP upload, info/Output pars).
  Copied into `runtime`; the socket client `helpers/vision_bridge/lib/camera_bridge.py` into `vision_client`.
- `test/test_depth_cam.py` - 36 offline tests (logic, static checks of builder/runtime/shader, runtime against a fake
  TD comp): `python3 -I -m unittest discover -s test -p 'test_depth_cam.py'` (also passes on TD's x86_64 Python).
- Needs only the helper binary (par `Helper`) and the model folder (par `Model`,
  `helpers/vision_bridge/assets/DepthAnythingV2SmallF16.mlmodelc`, git-ignored; provenance `assets/LICENSE-NOTICE.txt`).

## Network (stages)
Controls (zkit panel: Depth / Fog / Slice / Outline pages, `par_exec`) | 1 Source (`in_video`, `clip` =
`media/webcam/webcam_ref_5s.mp4` -> `src_switch` -> `src_flip` (Mirror) -> `src`) | 2 Vision bridge (`detect` 518x392
rgba8 -> `detect_bgra` Reorder TOP R<->B, `frame_exec`, `runtime`, `vision_client`, `depth_cam_logic`, `info` ->
`out_info`) | 3 Depth map (`depth_field` Script TOP mono32float -> `depth` -> `out_depth`) | 4 Effects (`fx` one
pixel GLSL pass, shader in docked `fx_pixel`, -> `out_video`).

## Outputs
- `out_video` (TOP, source size): `Mode` = Depth view (grey, 1 = near), Fog (far part fades into Fogcolour between
  Fogstart..Fogend farness), Slice (keeps a nearness band Slicecenter +- Slicewidth/2 with a soft edge; outside scaled by
  Sliceoutside, premultiplied, so 0 = transparent; Slicespeed sweeps the band far <-> near), Outline (depth-edge lines,
  Sobel-like central difference at Linewidth px, Linethresh = depth step; Lineonly = lines on transparent). `Mix`
  blends with the source. **No depth (Havedepth 0) = the source passes through untouched.**
- `out_depth` (TOP): the eased depth field, 518x392 mono 32-bit float, 0 far .. 1 near (relative per frame: 2 % / 98 %
  percentiles mapped to 0..1, eased over >= 0.25 s), stretched picture (ScaleFill), sample it by uv.
- `out_info` (DAT): status, helper pid, map size, range lo/hi, latency median/p95, compute ms, maps/s, answers,
  ignored, restarts, python ms per frame (all / answer frames), last error.

## Pars
Depth (panel): Active, Mode, Mix, Smooth (0 = raw, 1 = 0.6 s), Hold (s without answers before pass-through), Invert,
Mirror. Fog: Fogamount, Fogstart, Fogend, Fogcolour. Slice: Slicecenter, Slicewidth, Slicesoft, Slicespeed,
Sliceoutside. Outline: Linethresh, Linewidth, Lineonly, Linecolour. Setup: Source (clip / In TOP), Clipfile, Helper,
Model, Fakedepth (synthetic moving depth, no helper). Output (read-only): Status, Latency, Rate, Havedepth.
Zkit page (added by zkit): Opencontrols etc.

## Safety
- T-70: own `controls_window` closed before a rebuild, panel container never destroyed (zkit refreshes in place), every
  destroy through `safe_destroy`, network pane never moved, the running helper stopped first.
- T-74: the builder reads no pixels; the runtime reads `detect_bgra` only with `numpyArray(delayed=True)` (previous
  frame's download), skips the first 3 frames after every start, and `detect` is a fixed 518x392 rgba8 (never resized at
  run time). Readback frame id is the frame of the call (one frame younger than the picture; latency numbers include it).
- T-46: the effect is one pixel pass; nothing multi-pass. T-67: state in the runtime module, not op storage.
- Helper: spawned only while Active (`serve --no-seg --no-faces --no-landmarks --model <Model> --parent-pid <TD>
  --idle-exit 20`), never when the model folder is missing (status says so); Active off / rebuild terminates it (kill
  after 1 s); it also exits with TD or after 20 s idle; respawn backoff 0.5..8 s.

## Evidence so far (offline, 26 Oct 2026, M1 Max, macOS 27.0; nothing run in TD)
| Check | Result |
|---|---|
| Helper rebuilt arm64 (`build.sh` flags, scratch output, atomic swap) | Mach-O arm64, sha1 597fae9087dd (identical to the face_track build: only a comment changed) |
| Model copy | 5 files, 49,887,454 B, weight.bin sha1 086f4da2c878 = td-port's |
| Standalone, native python 3.13, as fast as one-in-flight allows (`depth_socket_test.py`, 150 frames of webcam_ref_5s at 518x392) | first model load at the new path 7.1 s (Core ML compiles its cache; 13 not-ready answers), then 101 ms; 150/150 answers, RTT median 38.0 / p95 51.5 ms, compute 35.9 / 47.5 ms, 19.6 maps/s |
| Same, TD's x86_64 Python 3.11 under Rosetta, paced 60 Hz poll (like a TD frame loop) | 62 answers over the 5 s clip, RTT median 58.6 / p95 67.3 ms (3.5 frames), compute 40.8 / 50.1 ms, 15.7 maps/s; numpy field step 0.41 ms median (p95 2.9) |
| Depth range (raw model values) | p2 0.059..0.081 (median 0.069), p98 0.864..0.949 (median 0.915) |
| Plausibility (frame 75, inspected by eye) | head and chair nearest (bright), ceiling and back wall far, lamp a separate blob; field mean 0.21; picture upright (bottom-up rows handled) |
| Readback conversion on TD's numpy | 0.47 ms with the GPU R/B swap (`bytes_from_bgra_float`) vs 2.5 ms for `camera_bridge.bgra_bytes` |
| Runtime end to end vs the real helper, fake TD comp, TD's Python, 60 Hz, 12 s | status ok in ~2 s; 15 maps/s; latency median 55 / p95 80 ms; python 0.33 ms/frame median, 2.2 ms on answer frames (incl. the fake readback's float conversion); helper SIGKILLed at 6 s -> Havedepth 0 at once, respawned, ok again ~2 s later, restarts 1; Active off -> helper gone |
| Shader, offline on the Mac GL 4.1 driver (td-port `offline_render/glsl_render.c` built in scratch, TD header stub; maths only, not TD) | Havedepth 0: max diff 0 vs source; Depth view mean = map mean (0.2065); Fog (defaults) mean change 0.359 on far pixels (depth < 0.2, 71 % of the frame) vs 0.002 on near ones (> 0.6); Slice (centre 0.7, width 0.3; defaults now 0.8 / 0.4 to keep the near person) alpha coverage 5.0 % vs 4.0 % of pixels in the band (soft edge adds the rest); Outline marks 5.2 % of pixels along the head, chair, lamp, ceiling edges |

## Live (26 Oct 2026, TD 2025.31550, M1 Max; T-92)
| Check | Result |
|---|---|
| Build | 30 ops, zkit panel 20 knobs 589x631, td_errors 0, layout ok (5 stages, no overlaps/back wires) |
| Active on, stored clip, 5 s | status ok, 16.5 maps/s, RTT median 55.6 / p95 56.8 ms, compute 38.5 ms, 126 answers, 0 ignored, 0 restarts; Python 0.18 ms/frame (3.4 on answer frames) |
| Script TOP upload | 1-channel float32 refused -> RGBA fallback (`upload4` True); TOP stays mono32float 518x392 |
| Depth view | depth mean 0.2106 (offline 0.2065), p2 0.002 / p98 0.98; fx (1920x1080) mean 0.2102 = map mean |
| Fog (defaults) | mean change 0.357 on far pixels (depth < 0.2, 71 %) vs 0.006 near (> 0.6) |
| Slice (0.8 / 0.4) | alpha coverage 8.2 % vs 8.9 % of pixels in band |
| Outline (Lineonly) | 3.7 % of pixels lit |
| Model path wrong | status "model missing: ...", no helper, Havedepth 0, out_video max diff 0 vs source |
| Active off | helper gone (pgrep), status off, Havedepth 0 |
| Cost / fps | clip (Movie File In 1080p) ~3 ms/frame CPU, fx 0.21 ms, depth_field ~0.9 ms per upload (16/s); project 60.2 fps avg (td_watch 5 s, min 59.6) |
| Not run | helper SIGKILL by PID (live kill not permitted in this lane; offline run showed respawn in ~2 s) |
| Capture | network + viewers, Fog mode (scratchpad dc_depth_cam_fog.png) |

Parked after the check (allowCooking off, Active off, Mode depth); saved as JazibTD_home.140.toe.

## To do live (done above except the kill test) (next lane, with TD free; one COMP, other lab COMPs parked)
1. Build, `td_errors`, `td_layout check`; Active on with the stored clip; read `out_info` (status ok, maps/s, latency).
2. Confirm on 31550: Script TOP accepts a 1-channel float32 `copyNumpyArray` into mono32float (fallback to RGBA is in
   the runtime: `info` would not show it; check `STATE[comp.id]['upload4']`); `numpyArray(delayed=True)` on the
   unviewed `detect_bgra` keeps returning new frames (if it returns None/stale, give it a consumer or a viewer).
3. Each Mode by eye + td_perf (fx GPU, depth_field upload, Python per frame) and project fps with the window open.
4. Kill the helper by PID, model path wrong, Active off: status + pass-through as offline.

## Not done
- Anything inside TD (above). Live camera (only on the user's ask). Metric depth (the model gives relative depth).
- Per-frame (GPU) smoothing between maps: the field is eased per answer (~15/s), as DepthLogic does.
