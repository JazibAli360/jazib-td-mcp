# FX_glitch

> fx_glitch: FX_glitch rack + 15 modules (smear pilot first; live in main, 26-27 Oct 2026, TD 2025.31550)

v0.3.1 - TD 2025.31550 - exported 2026-10-29 00:08:21 from `/project1/lab/FX_glitch`

`/project1/lab/FX_glitch`. The digital-breakage COMP from `docs/research/FX0_effects_backlog.md` (Phase 0 pilot). It
is kept lean on purpose (user rule 26 Oct: "dont bloat stuff just for modularity - it should make sense"): **no
codegen, no registry, no field/trigger/lib kit.** Those get built only when 2+ real modules need them. Module looks
come from `docs/research/FX1_destruction_datamosh_glitch.md` DG-05 / DG-06.

In: `in1` TOP. Out: `out1` TOP. Test picture: `test_clip` (the stored 5 s webcam clip, filled to 1080x1920; it cooks
only while selected). `Input` = auto (in1 once it is wired) / live / test.

Build doc: `docs/builds/fx_glitch.md`

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

cook 28.059 ms (CPU 28.059 / GPU 13.121) summed over the 46 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_glitch", "parent": "/project1/lab"}` (lands parked)
