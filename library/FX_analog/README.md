# FX_analog

> fx_analog_crt: FX_analog modules `crt` (+ `monitor` presets) and `crtfault` (offline prep, 26 Oct 2026)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:11 from `/project1/lab/FX_analog`

**Status: offline prep only. TD has not been touched.** Every claim below that needs TD is marked **LIVE CHECK**. A live
lane builds both modules and verifies them with the checks in this file (target about 15 minutes). Target build: TD
2025.31550.

| File | What |
|---|---|
| `builders/fx_analog_crt.py` | Module `crt`: PAGES (JZB_Lofi_CRT names), 8 zkit PRESETS, three compute shaders, `build(m, H)` |
| `builders/fx_analog_crtfault.py` | Module `crtfault`: PAGES, 5 PRESETS, one compute shader, `build(m, H)` |
| `builders/fx_analog_crt_logic.py` | Pure maths shared by both modules: raster, mask, warp, flicker, roll lock-in, Degauss, power, `clock_step`, the 13 MONITORS, numpy references `crt_ref` / `fault_ref`, the shared GLSL lib, clock / pulse callback texts, `save_snippet` + `check_dir` (CLI) |
| `test/test_fx_analog_crt.py` | 28 offline tests: `python3 -I -m unittest discover -s test -p 'test_fx_analog_crt.py'` (glslc compile included) |

Build doc: `docs/builds/fx_analog_crt.md`

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

cook 84.138 ms (CPU 84.138 / GPU 10.765) summed over the 22 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_analog", "parent": "/project1/lab"}` (lands parked)
