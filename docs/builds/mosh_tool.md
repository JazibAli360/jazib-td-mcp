# tools/mosh.py - offline datamosh / codec corruption (DG-03)

Offline media prep, no TouchDesigner. ffmpeg + Python 3 stdlib. Plan: `docs/research/FX1_destruction_datamosh_glitch.md` s3.3.
No safety limiter in the tool (user rule); check flashing yourself before a show.

## Method
Source -> MPEG-4 Part 2 elementary stream (`-bf 0`, huge GOP, keyframes only where asked) -> edit at VOP level
(start code `00 00 01 B6`, picture type = top 2 bits of the next byte, 0 = I, 1 = P) -> decode -> re-encode to a safe
delivery codec. MPEG-4 Part 2 tolerates cut-and-paste of frames; H.264 re-syncs at IDR and moshes badly.

## Commands
| Command | Does |
|---|---|
| `ifdrop IN OUT [--cuts 2,4] [--gop N] [--bsf]` | keyframes forced at the cut seconds, then all but the first dropped (clip motion drags across the cut). `--bsf` uses ffmpeg `-bsf:v noise=drop=gt(key,0)*gt(n,0)` instead of the Python edit. Output has one frame fewer per dropped keyframe. |
| `bloom IN OUT --at S --repeat N` | the P-frame at/after S seconds is repeated N extra times (+N frames): motion keeps pushing the picture. |
| `noise IN OUT [--amount 20000] [--seed 1]` | one random bit flip per `amount` bytes of payload (header untouched); deterministic per seed. |
| `transition A B OUT [--dur 2]` | A in full (its I-frame leads) then B's P-frames only, B's I-frame removed: B's motion drags A's last picture. Frames = A + B - 1. |
| `preset NAME IN OUT [--b B]` / `presets` | `drop_hold drop_cuts bloom_mid bloom_burst noise_light noise_heavy mosh_cut`. |
| `info FILE` | frame count, fps, size, picture-type counts. |

Common: `--size 480` (working/output width; height auto, vertical clips stay vertical), `--fps 30`, `--q 3`
(MPEG-4 quality), `--codec prores|hap|h264`, `--force` (refuses to overwrite otherwise).

## Delivery
ProRes 422 (`prores_ks` profile 2, 10-bit, `.mov` name required) is the default and loads in TD and Arena. `--codec hap`
needs an ffmpeg with the `hap` encoder; **this Mac's ffmpeg 8.1.2 has none**, so the tool prints a note and writes ProRes
(convert to HAP in Arena/TD if wanted). `--codec h264` is the small preview route. No further mosh is possible after
delivery (the codec damage is baked into pixels). Raise `--size` for full-res (1080 wide) deliveries; the working
resolution is the delivery resolution.

## Verified (26 Oct, ffmpeg 8.1.2)
`python3 -I -m unittest discover -s test -p test_mosh.py` -> 12 tests OK (~4.5 s), lavfi `testsrc2` / `mandelbrot`
clips, each output must decode with no errors: ifdrop 90 -> 88 frames (2 keyframes dropped), bloom 90 -> 120, transition
90+60-ish (checked 148..150), noise decodes, h264 route, overwrite guard, presets, CLI. Also run on
`media/demo/clips/tl_testsrc2_30fps_8s.mp4` (ifdrop 237 frames out of 240 in) and a red -> testsrc2 transition.

## Not done
ffglitch / Datamosher Pro (not installed; install = user's go-ahead), baked motion-vector export for DG-01 `Stored MV`,
HAP encode. Mosh results depend on content: static clips show little drag.
