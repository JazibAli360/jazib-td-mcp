# FX_synth

> FX_synth: video-synth rack + 6 modules (live in main, 26 Oct 2026, TD 2025.31550)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:34 from `/project1/lab/FX_synth`

Status: **built live in the main TD** (all six modules, slots left enabled 0, COMP parked, saved
JazibTD_home.362.toe, checkpoint `output/checkpoints/FX_synth/FX_synth_20261026-212428.tox`). Results: "Verified live"
at the end; the LIVE CHECKS below are the plan they answer. Specs: FX2 AV-22
(colorize), AV-23 + FX5 G24 (bands), AV-24 (keyer), AV-26 (ruttetra), AV-27 (scanimate), AV-28 (vfeedback), FX1 DG-22
(overflow); backlog FX0 rows 17-22. Rack + module template: `docs/builds/fx_glitch.md`.

`/project1/lab/FX_synth`. In: `in1` TOP. Out: `out1` TOP. The FX_glitch rack is reused unchanged, the same way
`builders/fx_analog.py` reuses it: the `slots` table, a Cross + Switch per slot, Panic, add/remove/rewire, the
`test_clip` input. `colorize1` is the first row. No module needs more than 3 GLSL inputs, so `_compute` is not
overridden.

Build doc: `docs/builds/fx_synth.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (passthrough) | Toggle | False | False |
| Input | Input | Menu | auto | auto |

## Perf

cook 99.977 ms (CPU 99.977 / GPU 2.508) summed over the 21 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_synth", "parent": "/project1/lab"}` (lands parked)
