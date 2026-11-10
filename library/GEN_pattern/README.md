# GEN_pattern

> gen_pattern: GEN_pattern rack + 17 one-pass generator modules (live in main, 26-27 Oct 2026, TD 2025.31550)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:44 from `/project1/lab/GEN_pattern`

`/project1/lab/GEN_pattern`. FX0 row "GEN_pattern" (backlog ranks 37, 38, 64, 65, 68, 80): research cards FX5 G06
truchet, G17 opart, G07 wallpaper, G28 domainwarp, G29 gyroid, G27 cymatics, E7/G30 split, G20/E2 barcode, E5/G35
columns, G16 + FX4 G-KALEIDO2 / G-INFZOOM kaleido2 / droste / infzoom. Everything below was written and tested
offline (no TD tools); the LIVE CHECKS section is the job for the live lanes, with the numbers they must hit.

**Status: live on 2025.31550 (built in b3, in the main .toe): all 12 modules verified, see "Verified live". 18 offline
tests; every shader compiles with `glslc` (OpenGL target, TD-like prelude).**

Build doc: `docs/builds/gen_pattern.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (background only) | Toggle | False | False |
| Input | Input | Menu | auto | auto |
| Resw | Width | Int | 1080 | 1080 |
| Resh | Height | Int | 1920 | 1920 |

### Drive

| name | label | style | default | value |
|---|---|---|---|---|
| Beatsource | Beatsource | Menu | internal | internal |
| Bpm | Bpm | Float | 120.0 | 120.0 |
| Bpmchop | Bpm CHOP (e.g. AU_features/out1) | CHOP |  |  |
| Bpmchan | Bpm channel | Str | bpm | bpm |
| Beatchop | Beat CHOP (e.g. AU_features/out1) | CHOP |  |  |
| Phasechan | Beat phase channel | Str | beat_phase | beat_phase |
| Countchan | Beat count channel | Str | beat_count | beat_count |
| Audiochop | Audio CHOP (e.g. AC_audio/out_ctl) | CHOP |  |  |
| Audiochan | Audio channel | Str | low | low |
| Resync | Resync (beat 1 now) | Pulse | False | False |

## Perf

cook 25.346 ms (CPU 25.346 / GPU 1.387) summed over the 26 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GEN_pattern", "parent": "/project1/lab"}` (lands parked)
