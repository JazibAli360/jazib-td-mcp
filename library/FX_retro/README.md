# FX_retro

> fx_retro: FX_retro rack + 5 modules (palette, dither, glyph, teletext, smalldisplay), live in main, 26 Oct 2026

v0.4.0 - TD 2025.31550 - exported 2026-10-29 00:08:26 from `/project1/lab/FX_retro`

`/project1/lab/FX_retro`: retro machines and displays. The rack is the lean FX_glitch rack, copied as FX_destroy did
(template: `docs/builds/fx_glitch.md`). Research: `docs/research/FX0_effects_backlog.md` rows 23 / 59 / 60 / 78,
`docs/research/FX2_analog_video_hardware_emulation.md` AV-34, 35, 38, 39 and 40, FX5 G21 / G25, FX3 S4.
**Status: LIVE on 31550** (built module by module on build TD b2, brought home into the main .toe, parked, saved):
every LIVE CHECK passes ("Verified live" below; live fixes in LEARNINGS T-141). Offline status:
`python3 -I -m unittest discover -s test -p 'test_fx_retro.py'` passes 57 tests. They cover the logic, the palette_map
reuse, the numpy references used by the live checks, the Script CHOP adapters on fakes, a dry build of every module on
a fake TD with the rack's real helpers, and a glslc compile (OpenGL target, TD stubs) of all 7 compute shaders.

Build doc: `docs/builds/fx_retro.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (passthrough) | Toggle | False | False |
| Input | Input | Menu | auto | auto |

### About

| name | label | style | default | value |
|---|---|---|---|---|
| Version | Version | Str |  | 0.4.0 |
| Touchbuild | Touch build | Str |  | 2025.31550 |
| Saved | Saved | Str |  | 2026-10-26 21:55 |

## Perf

cook 28.321 ms (CPU 28.321 / GPU 10.295) summed over the 16 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_retro", "parent": "/project1/lab"}` (lands parked)
