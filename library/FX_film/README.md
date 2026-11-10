# FX_film

> fx_film: FX_film rack + 14 modules (film, lens, camera, dof, gate, colour), live in main, 26-27 Oct 2026

v1.0.0 - TD 2025.31550 - exported 2026-10-29 00:08:16 from `/project1/lab/FX_film`

`/project1/lab/FX_film`. The film / lens / colour COMP from `docs/research/FX0_effects_backlog.md` (rows 26-32,
FX3 F1-F4, F7, L1-L5, S4). **Status: LIVE on 31550** (built module by module on build TD b2, brought home into the
main .toe, parked, saved): all 10 wave A/B modules pass their LIVE CHECKS ("Verified live" below); wave C (camera,
dof, gate, colour) live on b4 and brought home 26 Oct ("Verified live (wave C)"; polish 27 Oct: dof highlight sprites pass DF3 polygon, camera Trail fused pass). Target ms in the module table
are the prep's targets; measured costs are in "Verified live". The rack is the lean `FX_glitch` rack (template
`docs/builds/fx_glitch.md`), copied, not abstracted.

In: `in1` TOP. Out: `out1` TOP. Rack page: `Panic`, `Input` = auto / live / test clip / **test chart**, `Chart` =
lights (5 discs r 6 px at value `Chartvalue` 4.0 on `Chartbg` 0) / ramp (x ramp 0..1 bottom half, x 0.1 top half) /
grey (`Chartgrey`) / patches (6 x 4 linear patches incl. HDR row). The chart is `rgba16float`, so the chain is 16F
while it is selected (glow energy is not clipped by 8 bits). Positions: `fx_film_logic.LIGHTS`, `PATCHES`.

Build doc: `docs/builds/fx_film.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (passthrough) | Toggle | False | False |
| Input | Input | Menu | auto | auto |
| Chart | Chart | Menu | lights | lights |
| Chartvalue | Chart light value | Float | 4.0 | 4.0 |
| Chartbg | Chart background | Float | 0.0 | 0.0 |
| Chartgrey | Chart grey | Float | 0.5 | 0.5 |

### About

| name | label | style | default | value |
|---|---|---|---|---|
| Version | Version | Str |  | 1.0.0 |
| Touchbuild | Touch build | Str |  | 2025.31550 |
| Saved | Saved | Str |  | 2026-10-26 21:12 |

## Perf

cook 29.18 ms (CPU 29.18 / GPU 1.867) summed over the 18 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_film", "parent": "/project1/lab"}` (lands parked)
