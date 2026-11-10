# FX_glass

> fx_glass: FX_glass rack + modules (lane B, 27 Oct 2026, TD 2025.31550 target)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:18 from `/project1/lab/FX_glass`

`/project1/lab/FX_glass`. Glass / lens surfaces over any picture: liquid glass (pilot), holo foil, rain on glass, frost
/ reeded / fly-eye, wet mirror floor (BUILD_PLAN_27OCT s2: its own rack, not FX_film, to keep FX_film's bring-home
light). Specs = research rows SX-01 / SX-02 / SX-03 (`docs/research/FX7a_shadertoy_glsl_libraries.md`), 7C-21 / 22 /
23 / 34 (`FX7c_other_tools_effects.md`).

Build doc: `docs/builds/fx_glass.md`

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

cook 28.236 ms (CPU 28.236 / GPU 0.175) summed over the 9 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_glass", "parent": "/project1/lab"}` (lands parked)
