# face_track - `/project1/lab/FT_face_track` (TD 2025.31550, 26 Oct 2026)

Clean-room take on vankrav's "Face Tracking" rudiment (spec: `docs/research/BH_rudiment_face_tracking.md`).
Apple Vision face landmarks from a native arm64 helper (`helpers/vision_bridge`, kind 5) -> CHOPs, masks, wire overlay.

## Files
- `builders/face_track.py` - builder, `build(parent_path='/project1/lab', name='FT_face_track', regen_ui=False)`, run via td_exec:
  `g = dict(globals()); exec(open('<repo>/builders/face_track.py').read(), g); g['build']('/project1/lab')`
- `builders/face_track_logic.py` - pure logic (parse, measures, One-Euro, tracker, polygons, wire); tests
  `test/test_face_track.py` (27, offline).
- `builders/face_track_runtime.py` - TD glue (frame pump, helper lifecycle, Script CHOP cooks). Logic, runtime and
  the socket client are copied into Text DATs: the COMP needs only the helper binary (par `Helper`).

## T-70 safety (rebuilt after the 13:12 crash)
The builder closes the COMP's own `controls_window` first, never destroys the `controls` container (widgets are
regenerated in place only with `regen_ui=True` or when it is empty), every destroy goes through the MCP's
`safe_destroy`, and it never moves the network pane. Rebuild with the window open + `regen_ui=True`: window closed, no crash.

## Outputs
- `out_video` (TOP): source + wire (brows, eyes + pupils, nose, nose crest, median line, lips, jaw); no face = input passes
  through bit-exact (max diff 0).
- `out_face`, `out_eyes`, `out_mouth` (mono TOPs, Maskres wide, blur `Maskblur`): one compute GLSL pass (T-46/T-47).
- `out_pts` (CHOP): `f<n>_<region>_<kk>x/y`, 0..1, origin top-left, 174 channels per face, zeros when absent.
- `out_ctl` (CHOP): `facecount` + per face `present slot_id conf x y w h cx cy size roll roll_vision yaw pitch
  eye_open_l/r eye_l_raw eye_r_raw mouth_open mouth_raw smile`. `roll` = eye line (deg/rad by `Rollunit`); `roll_vision`
  is Vision's own value and is noisy on partial faces (-84..-10 deg on the webcam clip while the eye line said -13..+6).
- `out_info` (DAT): status, helper pid, latency, compute ms, answers/s, restarts, python ms/frame.

## Pars
Track (panel): Active, Maxfaces 1-32 (default 4), Smooth, Minconf, Holdframes, Mirror, Showwire, Showboxes, Wirewidth, Wireopacity,
Maskblur, Maskgrow, Eyeexpand, Mouthexpand, Forehead, Opencontrols. Setup: Source (clip / In TOP), Clipfile (default
`media/webcam/webcam_ref_5s.mp4`), Detectsize 480/640/960, Maskres, Rollunit, Helper, Eyeclosed/Eyeopen/Mouthrest/Mouthmax,
Calibrate (rest pose of face 1), Fakeface. Colours: Wirecolor. Output (read-only): Facecount, Latency, Status.

## Verified live (26 Oct, 31550, M1 Max)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
| Check | Result |
|---|---|
| Helper standalone (arm64) | 1.0 s to first answer; RTT median 20 ms, compute 17.7 ms at 640x360; multi-face clip 2 faces |
| webcam_ref_5s.mp4 in TD | answers with a face 114/351 = 32 % (standalone 37 %: the face is cut by the bottom edge most of the clip); wire on the face, landmark y order brow 0.87 < eye 0.91 < nose 0.98 < lips 1.03 |
| Full-face demo clip (`media/demo/faces/ward_cunningham_8s.mp4`) | every face-segment answer had the face (0-6 s); 6-8 s cutaway: present ramps 0.83, 0.67, 0.5, 0.33, 0.17, 0 after Holdframes; f1_w 0.24-0.28, roll -4.6..+2.8 deg |
| Two faces (`..._twofaces.mp4`, Maxfaces 2) | raw 2 faces per answer, facecount 2, 0 slot side swaps over 128 frames |
| Masks | mask mean = polygon area: face 0.09114 vs 0.09113, eyes 0.00206 vs 0.00206, mouth 0.00365 vs 0.00365; 0 eye/mouth px outside the face mask; mouth mask 0.0027 -> 0.0044 as mouth_open 0.05 -> 0.46 |
| Smoothing | mean per-answer change, Smooth 0 vs 0.8: roll 0.29 -> 0.18 deg, cx 0.0020 -> 0.0008, eye ratio 0.0091 -> 0.0031, mouth 0.055 -> 0.025 |
| Fake face | whole chain runs with the helper off; mask areas match the polygons |
| Helper killed (SIGKILL by PID) | respawned within 3 s, restarts 1, tracking again, no errors |
| Helper missing (bad path) | status "helper missing: ...", facecount 0, video pass-through exact, masks black, no errors |
| Active off | helper process gone (ps), status off, outputs zero |
| Calibrate | Eyeopen/Eyeclosed/Mouthrest captured on the next frame (pulse via Parameter Execute) |
| Perf | python 2.7-3.1 ms per frame (median), helper RTT median 16-34 ms (34 under other agents' load), 20-29 answers/s at 60 fps (one in flight); GPU: overlay 0.40 ms, mask pass 0.75 ms, blur 0.29 ms |
| td_errors / layout check | clean / ok (no intruders, unboxed, box overlaps) |

## Notes / left
- The webcam reference clip shows only the top of the face most of the time; full-face checks used the demo clip.
- GLSL TOPs cook on pull (Out TOPs not consumed = no GPU cost).
- Not done: live camera (only on the user's ask), Source = In TOP from another COMP, MediaPipe/Windows backends (FUTURE).
