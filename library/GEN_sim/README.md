# GEN_sim

> gen_sim: GEN_sim rack + 5 modules `ca` / `voronoi` / `dla` / `blobs` / `lic` (live in main, 26 Oct 2026, TD 2025.31550)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:52 from `/project1/lab/GEN_sim`

**Status: live in the main TD (26 Oct, 31550), all 5 modules; results in "Verified live" at the end.** Every claim
that needed TD was a **LIVE CHECK** (table near the end, with the numbers expected). Offline: 70 tests (`python3 -I -m unittest discover -s test -p
'test_gen_sim*.py'`, ~9 s), every compute pass compiles with `glslc` against stubs of TD's compute built-ins (a
syntax and type check, not a TD compile), and numpy references in `builders/gen_sim_logic.py` mirror every pass.

`/project1/lab/GEN_sim`. The simulation-generator COMP from `docs/research/FX0_effects_backlog.md` row GEN_sim
(FX5 G08 / G26 CA lab, G10 Voronoi / JFA, G09 Laplacian growth, G12 blobs, G02 LIC). Lean on purpose (user rule 26
Oct, "dont bloat stuff just for modularity"): the rack is `builders/fx_glitch.py` reused as is, the way
`builders/fx_analog.py` does it, plus a small generator variant.

| File | What |

Build doc: `docs/builds/gen_sim.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (background only) | Toggle | False | False |
| Input | Input | Menu | auto | auto |
| Resw | Width (black bg) | Int | 1080 | 1080 |
| Resh | Height (black bg) | Int | 1920 | 1920 |

## Perf

cook 46.939 ms (CPU 46.939 / GPU 1.331) summed over the 16 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GEN_sim", "parent": "/project1/lab"}` (lands parked)
