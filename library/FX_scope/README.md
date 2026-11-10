# FX_scope

> fx_scope: FX_scope rack + 5 modules `xy` `vector` `lissajous` `scopes` `hud` (live in main, 26 Oct 2026)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:29 from `/project1/lab/FX_scope`

`/project1/lab/FX_scope`. FX0 Phase 4 lane C (`docs/research/FX0_effects_backlog.md` rows 25, 58; FX2 AV-30..33, FX3 C6,
FX5 G19 / G38). Scopes, vector displays and the camera HUD, as one rack. **Built live 26 Oct (31550): all five
modules in the main .toe, see "Verified live" for which LIVE CHECKS ran and their numbers.** Offline status: `python3 -I -m unittest discover -s test -p 'test_fx_scope*.py'`
(39 tests: specs, presets, every par expression evaluated on a fake TD, numpy references, glslc compile of all 14
shaders x 4 build switches, dry builds on a fake TD). One owner: the FX_scope prep lane (T-119); every file is
`fx_scope*`.

Build doc: `docs/builds/fx_scope.md`

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

cook 29.096 ms (CPU 29.096 / GPU 1.197) summed over the 9 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_scope", "parent": "/project1/lab"}` (lands parked)
