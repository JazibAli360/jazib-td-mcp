# FX_stylise

> fx_stylise: FX_stylise rack + modules (lane B, 27 Oct 2026, TD 2025.31550 target)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:31 from `/project1/lab/FX_stylise`

`/project1/lab/FX_stylise`. Image stylise filters used on a different layer from FX_film (BUILD_PLAN_27OCT s2: FX7a
FX_stylise + FX7c FX_paint + backlog #71 in one rack). Specs = research rows: SX-05 / SX-06 / SX-07
(`docs/research/FX7a_shadertoy_glsl_libraries.md`), 7C-01 / 02 / 04 / 05 / 09 (`FX7c_other_tools_effects.md`), #71
(`FX0_effects_backlog.md`). Order: outline (pilot) -> boil -> ink -> saber -> clean -> watercolour -> engrave -> kuwahara.

Build doc: `docs/builds/fx_stylise.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (passthrough) | Toggle | False | False |
| Input | Input | Menu | auto | test |

## Perf

cook 28.879 ms (CPU 28.879 / GPU 10.471) summed over the 12 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_stylise", "parent": "/project1/lab"}` (lands parked)
