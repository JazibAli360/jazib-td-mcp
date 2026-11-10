# GEN_sdf

> gen_sdf: GEN_sdf rack + 10 raymarch / fractal / sky modules (live in main, 26-27 Oct 2026, TD 2025.31550)

v0.3.0 - TD 2025.31550 - exported 2026-10-29 00:08:50 from `/project1/lab/GEN_sdf`

`/project1/lab/GEN_sdf`. FX0 rows 41 (SDF raymarch toolkit) + 67 (fractal explorer), FX0 "GEN_sdf" line; FX5 G13
(sdfscene with preset scenes) + G14 (Mandelbulb / Mandelbox / Julia / 2D with deep zoom). Research and sources:
`docs/research/BS_sdf_raymarch_fractals.md`.

**Status: live on 2025.31550 (built in b5, in the main .toe `JazibTD_home.388.toe`): 3 modules, 21 presets verified,
see "Verified live" (+ "Perf pass" below it). 19 offline tests; every shader compiles with glslc.**

Build doc: `docs/builds/gen_sdf.md`

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
| Bpm | Bpm | Float | 120.0 | 0.0 |
| Bpmchop | Bpm CHOP (e.g. AU_features/out1) | CHOP |  |  |
| Bpmchan | Bpm channel | Str | bpm | bpm |
| Beatchop | Beat CHOP (e.g. AU_features/out1) | CHOP |  |  |
| Phasechan | Beat phase channel | Str | beat_phase | beat_phase |
| Countchan | Beat count channel | Str | beat_count | beat_count |
| Audiochop | Audio CHOP (e.g. AC_audio/out_ctl) | CHOP |  |  |
| Audiochan | Audio channel | Str | low | low |
| Resync | Resync (beat 1 now) | Pulse | False | False |

## Perf

cook 0.533 ms (CPU 0.533 / GPU 5.899) summed over the 21 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GEN_sdf", "parent": "/project1/lab"}` (lands parked)
