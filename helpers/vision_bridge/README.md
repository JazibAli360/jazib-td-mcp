# helpers/vision_bridge - native arm64 Apple Vision helper for TD (face landmarks)

Copy of `td-port/camera_bridge` (td-port is a separate project: never edited from here; provenance in the header of
`src/jzb_vision_bridge.mm`, `lib/camera_bridge.py`, `build.sh`). Added here: request **kind 5 = face landmarks**
(`VNDetectFaceLandmarksRequest` revision 3, constellation 76) for `builders/face_track.py`. Built with the user's
go-ahead (26 Oct 2026). **Kind 1 = depth** (td-port's Core ML Depth Anything V2 Small request, unchanged) is used by
`builders/depth_cam.py` since 26 Oct: the compiled model is copied into `assets/` (below).

## Why arm64 only
TD 2 (2025.31550) runs as x86_64 under Rosetta, and its bundled Python has no Vision/pyobjc/mediapipe. The helper is a
separate native arm64 process (Vision runs natively); TD talks to it over a Unix-domain socket. A translated (x86_64)
helper is not wanted.

## Build / standalone test
```sh
sh helpers/vision_bridge/build.sh            # clang++ arm64, ad-hoc signed, prints sha1
ffmpeg -i media/webcam/webcam_ref_5s.mp4 -vf scale=640:-2,vflip -pix_fmt bgra -f rawvideo /tmp/frames.bgra
python3 -I helpers/vision_bridge/landmarks_socket_test.py /tmp/frames.bgra 640 360 /tmp/out.json
```
Measured 26 Oct (M1 Max, native python 3.13): first answer 1.0 s after spawn, round trip median 20 ms (p95 39),
Vision compute median 17.7 ms at 640x360; webcam_ref_5s: face on 55/150 frames (the face is cut by the bottom edge
for the rest), y order eyes < nose < lips < jaw on 55/55; a two-face side-by-side clip: 2 faces on every face frame.

## Depth model (kind 1)
`assets/DepthAnythingV2SmallF16.mlmodelc` (git-ignored, 5 files, 49.9 MB) copied read-only from
`td-port/camera_bridge/assets/` with its licence (`assets/LICENSE-Apache-2.0.txt`) and provenance
(`assets/LICENSE-NOTICE.txt`: Apple's Core ML conversion of Depth Anything V2 Small, Apache-2.0). Default model path =
`build/../assets/...`; `--model` overrides. Answer: float32 518x392 (the model's size, whatever the request size;
ScaleFill), rows bottom-up, larger = nearer, header pLo/pHi = 2 % / 98 % percentiles.
```sh
ffmpeg -i media/webcam/webcam_ref_5s.mp4 -vf scale=518:392,vflip -pix_fmt bgra -f rawvideo <scratch>/frames518.bgra
python3 -I helpers/vision_bridge/depth_socket_test.py <scratch>/frames518.bgra 518 392 <scratch>/out [paced]
```
Measured 26 Oct (M1 Max): first load at a new model path 7.1 s (Core ML cache compile), 0.1 s after; native client RTT
median 38 ms (compute 36 ms, 19.6 maps/s); TD's x86_64 Python paced at 60 Hz: RTT median 58.6 ms, 15.7 maps/s.
Numbers and checks: `docs/builds/depth_cam.md`.

## Protocol (kind 5)
Same 48-byte request header as td-port (`lib/camera_bridge.py` `pack_request`), BGRA payload, `FL_BOTTOM_UP` for TD
`numpyArray()` rows. Answer float32, w = 9 + 2 * points, h = faces: x y w h (boundingBox, origin bottom-left), roll
yaw pitch (radians, NaN when absent), face conf, landmarks conf, then every point (x, y) normalized 0..1 in IMAGE space,
origin bottom-left. Answer text = JSON `{"regions": [[name, count], ...]}` (jaw 17, brow_l 6, brow_r 6, eye_l 6,
eye_r 6, pupil_l 1, pupil_r 1, nose 8, nosecrest 6, median 10, lips_outer 14, lips_inner 6 = 87 points).
`eye_l` / `brow_l` / `pupil_l` = Vision's `leftEye` etc., which lands on the IMAGE-left side in our tests.

## Lifecycle
depth_cam: spawned only while DC_depth_cam is Active and its model folder exists (`serve ... --no-seg --no-faces
--no-landmarks --model <Model>`); its own socket (`jzbcb_<uid>_dc<id>.sock`), so it runs beside face_track's helper.
face_track: spawned by the client only while the face_track COMP is Active (`serve --socket ... --parent-pid <TD> --idle-exit 20
--no-depth --no-seg --no-faces`); Active off / rebuild terminates it (then kill after 1 s); it also exits on its own
when TD dies or after 20 s without requests. Kill only by exact PID.
