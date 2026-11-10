# FX_trans

> fx_trans: FX_trans, the G-TRANS transition bank, 53 transition types (27 at first live) (live in main, 26 Oct 2026, TD 2025.31550)

v0.3.0 - TD 2025.31550 - exported 2026-10-29 00:08:37 from `/project1/lab/FX_trans`

`/project1/lab/FX_trans`: transitions from picture A to picture B for live shows. Research: `docs/research/FX0_effects_backlog.md`
row 69 (and rows 3 / 15: mosh cut, CRT power-off), `docs/research/FX4_software_fx_emulation.md` 1.8 (Arena transition
mixers, gl-transitions gap), the Notch / Universe transition lists there.
**Status: LIVE on b5 (31550, 26 Oct 2026), brought home into main (JazibTD_home.442.toe, 412 ops, 0 errors, parked).**
All LIVE CHECKS T1-T13 ran; see "Verified live" below. `python3 -I -m unittest discover -s test -p 'test_fx_trans.py'`
passes 34 tests (~6 s): source parse, wrapper, perf patches apply, progress / tempo / easing maths, the per-cook `chan`
cache, knob relabel, numpy references (wipe, circle, matte, fadecolor), the TV-off port checked against
`fx_analog_crt_logic.power_shape`, a dry build on a fake TD (with the moshcut sub-COMP), and a glslc compile of the
whole bank shader and of each of the 27 one-type shaders.

Build doc: `docs/builds/fx_trans.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- in `in3` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Trans

| name | label | style | default | value |
|---|---|---|---|---|
| Type | Type | Menu | fade | fade |
| Progress | Progress A -> B | Float | 0.0 | 0.0 |
| Drive | Drive | Menu | manual | manual |
| Go | Go (to the other side) | Pulse | False | False |
| Back | Back to A | Pulse | False | False |
| Cut | Cut (instant) | Pulse | False | False |
| Duration | Duration s | Float | 2.0 | 2.0 |
| Beats | Beats | Float | 4.0 | 4.0 |
| Ease | Ease | Menu | smooth | smooth |
| Steps | Steps (0 = continuous) | Int | 0 | 0 |
| Backstyle | Backstyle | Menu | rewind | rewind |
| Quantize | Quantize | Menu | off | off |
| Randompool | Random type per Go (ids, or all) | Str |  |  |

### Knobs

| name | label | style | default | value |
|---|---|---|---|---|
| K1 | K1 - | Float | 6.0 | 6.0 |
| K2 | K2 - | Float | 10.0 | 10.0 |
| K3 | K3 - | Float | 0.18 | 0.18 |
| K4 | K4 - | Float | 0.6 | 0.6 |
| K5 | K5 - | Float | 0.7 | 0.7 |
| K6 | K6 - | Float | 1.0 | 1.0 |
| K7 | K7 - | Float | 0.6 | 0.6 |
| K8 | K8 - | Float | 0.0 | 0.0 |
| K9 | K9 - | Float | 0.0 | 0.0 |
| K10 | K10 - | Float | 0.0 | 0.0 |
| Keepknobs | Keep knob values on Type change | Toggle | False | False |
| Resetknobs | Knobs to type defaults | Pulse | False | False |

### Tempo

| name | label | style | default | value |
|---|---|---|---|---|
| Bpm | BPM (when no CHOP) | Float | 120.0 | 120.0 |
| Bpmchop | BPM CHOP path (optional) | Str |  |  |
| Bpmchan | BPM channel | Str | bpm | bpm |
| Phasechan | Beat phase channel 0..1 (optional, Quantize) | Str |  |  |

### Input

| name | label | style | default | value |
|---|---|---|---|---|
| Asource | Asource | Menu | auto | auto |
| Bsource | Bsource | Menu | auto | auto |
| Mattesource | Mattesource | Menu | auto | auto |
| Mattetop | Matte TOP path | Str |  |  |
| Resw | Width | Int | 1080 | 1080 |
| Resh | Height | Int | 1920 | 1920 |
| Fit | Fit | Menu | fitoutside | fitoutside |
| Outside | Outside | Menu | hold | hold |
| Compile | Compile | Menu | bank | bank |

### State

| name | label | style | default | value |
|---|---|---|---|---|
| Gofrom | Run from (internal) | Float | 0.0 | 0.0 |
| Goto | Run to (internal) | Float | 1.0 | 1.0 |
| Gotime | Run start absTime (internal) | Float | -1.0 | -1.0 |
| Godur | Run seconds (internal) | Float | 0.0 | 0.0 |
| Goswap | Run swaps A/B (internal) | Float | 0.0 | 0.0 |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Speed | Float | 0.0 | 0.667 |
| Zkm2 | Snap | Float | 0.0 | 0.0 |

## Perf

cook 38.541 ms (CPU 38.541 / GPU 2.234) summed over the 16 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_trans", "parent": "/project1/lab"}` (lands parked)
