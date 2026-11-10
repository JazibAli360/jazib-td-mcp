# GEN_points

> gen_points: GEN_points rack + 8 point-engine modules (live in main, 26 Oct 2026, TD 2025.31550)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:47 from `/project1/lab/GEN_points`

`/project1/lab/GEN_points`. FX0 row "GEN_points" (backlog 40, 44, 66, 67); cards FX5 G04 density2d, G03 attractor3d,
G01 streamlines, FX4 G-FORM form (wave 1); FX5 G15 flame, G05 lsystem, G22 graph, G-SPARKLE sparkle (wave 2, FX0 rows
66 / 67). Research + maths: `docs/research/FX7_gen_points_sources.md`. Not built yet: Particular modules (G-PART2).

**Status: live on 2025.31550, 8 modules (built in b3, brought home into main; see "Verified live" and "Wave 2 + cost
pass"). 23 offline tests; every shader compiles with glslc.**

Build doc: `docs/builds/gen_points.md`

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

cook 4.152 ms (CPU 4.152 / GPU 10.262) summed over the 36 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GEN_points", "parent": "/project1/lab"}` (lands parked)
