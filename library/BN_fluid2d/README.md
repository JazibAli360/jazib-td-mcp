# BN_fluid2d

> fluid2d: BN_fluid2d 2D fluid COMP (live-verified v1 in main, 26 Oct 2026, TD 2025.31550, T-91)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:02 from `/project1/lab/BN_fluid2d`

`/project1/lab/BN_fluid2d`. A self-contained stable-fluids COMP: dye + velocity, wall / wrap / open edges, obstacle
mask, external force, 8 emitters driven by manual / BPM / audio / in4 points. Every multi-step pass is a **compute**
GLSL TOP (T-46/T-47); no pixel-mode chain anywhere. Spec: `docs/research/BN_fluid_cloth_sims.md` section 5
(clean-room). **No limits** (user rule): open ranges, no luminance / flash guard.

Everything below marked **LIVE CHECK** is a TD fact this offline prep could not confirm; the live lane confirms it and
writes the answer (and any bug) to `LEARNINGS.md` at once.

Build doc: `docs/builds/fluid2d.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- in `in3` (inTOP) 128x128
- in `in4` (inCHOP)
- in `in5` (inCHOP)
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 192x342
- out `out3` (outCHOP)

## Custom parameters

### Sim

| name | label | style | default | value |
|---|---|---|---|---|
| Simh | Sim cells (height) | Int | 456 | 342 |
| Resw | Dye width | Int | 1080 | 1080 |
| Resh | Dye height | Int | 1920 | 1920 |
| Iterations | Pressure iterations (rebuild) | Int | 20 | 8 |
| Relax | Jacobi weight | Float | 0.8 | 0.8 |
| Dtmode | Time step | Menu | auto | auto |
| Dt | Dt s | Float | 0.0166667 | 0.0166667 |
| Timescale | Time scale | Float | 1.0 | 1.0 |
| Veldiss | Velocity decay /s | Float | 0.2 | 0.2 |
| Dyediss | Dye decay /s | Float | 1.0 | 1.0 |
| Curl | Vorticity | Float | 30.0 | 30.0 |
| Edge | Edges | Menu | wall | wall |
| Warmstart | Pressure carry-over | Float | 0.8 | 0.8 |
| Quality | Quality | Menu | balanced | balanced |
| Idlesleep | Sleep when idle | Toggle | True | True |
| Status | Status | Str |  | idle: nothing drives it - wire in1 (dye) or in3 (force), Effectors on, Audio or BPM Internal (a dropped copy starts here) |

### Input

| name | label | style | default | value |
|---|---|---|---|---|
| Srcgain | Source gain (in1) | Float | 1.0 | 1.0 |
| Maskthresh | Mask threshold (in2) | Float | 0.5 | 0.5 |
| Forcegain | Force gain (in3) | Float | 1.0 | 1.0 |
| Emitradius | Emitter radius | Float | 0.03 | 0.03 |
| Emitforce | Emitter force | Float | 1.0 | 1.0 |
| Emitcolorr | Emitter colour | RGBA | 1.0 | 1.0 |
| Emitcolorg | Emitter colour | RGBA | 0.4 | 0.4 |
| Emitcolorb | Emitter colour | RGBA | 0.1 | 0.1 |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiomode | Audio | Menu | off | off |
| Audiogain | Audio gain | Float | 4.0 | 4.0 |
| Lowhz | Low band Hz | Float | 150.0 | 150.0 |
| Burstthresh | Kick threshold | Float | 0.3 | 0.3 |
| Burstrefractory | Kick refractory s | Float | 0.15 | 0.15 |
| Bpmmode | BPM | Menu | off | off |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Bpmdiv | Burst every | Menu | b1 | b1 |
| Bpmpattern | Burst pattern | Menu | ring | ring |
| Beatchop | Beat CHOP (external) | CHOP |  |  |
| Burst | Burst | Pulse | False | False |
| Burstforce | Burst force | Float | 1.0 | 1.0 |
| Burstring | Burst ring radius | Float | 0.12 | 0.12 |
| Burstradius | Burst splat radius | Float | 0.04 | 0.04 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Colormode | Colour | Menu | rgb | rgb |
| Exposure | Exposure (stops) | Float | 0.0 | 0.0 |
| Gamma | Gamma | Float | 1.0 | 1.0 |
| Speedref | Speed for top colour (cells/s) | Float | 300.0 | 300.0 |
| Dyeblend | Dye blend | Menu | add | add |
| Alpha | Alpha | Menu | opaque | opaque |
| Premult | Premultiplied | Toggle | True | True |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |
| Pal1r | Palette 1 (low) | RGBA | 0.05 | 0.05 |
| Pal1g | Palette 1 (low) | RGBA | 0.05 | 0.05 |
| Pal1b | Palette 1 (low) | RGBA | 0.25 | 0.25 |
| Pal2r | Palette 2 | RGBA | 0.35 | 0.35 |
| Pal2g | Palette 2 | RGBA | 0.1 | 0.1 |
| Pal2b | Palette 2 | RGBA | 0.65 | 0.65 |
| Pal3r | Palette 3 | RGBA | 0.95 | 0.95 |
| Pal3g | Palette 3 | RGBA | 0.2 | 0.2 |
| Pal3b | Palette 3 | RGBA | 0.55 | 0.55 |
| Pal4r | Palette 4 | RGBA | 1.0 | 1.0 |
| Pal4g | Palette 4 | RGBA | 0.6 | 0.6 |
| Pal4b | Palette 4 | RGBA | 0.15 | 0.15 |
| Pal5r | Palette 5 (high) | RGBA | 1.0 | 1.0 |
| Pal5g | Palette 5 (high) | RGBA | 1.0 | 1.0 |
| Pal5b | Palette 5 (high) | RGBA | 0.9 | 0.9 |

### Control

| name | label | style | default | value |
|---|---|---|---|---|
| Reset | Reset | Pulse | False | False |
| Pause | Pause | Toggle | False | False |
| Step | Step (while paused) | Pulse | False | False |
| Stopat | Pause at step (0 = off) | Int | 0 | 0 |
| Seed | Seed | Int | 1 | 1 |
| Testmode | Test mode | Menu | off | off |

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
| Zkm1 | Swirl | Float | 0.0 | 0.5 |
| Zkm2 | Persist | Float | 0.0 | 0.5 |
| Zkm3 | Force | Float | 0.0 | 0.5 |
| Zkm4 | Size | Float | 0.0 | 0.5 |

### About

| name | label | style | default | value |
|---|---|---|---|---|
| Version | Version | Str |  | 0.1.0 |
| Touchbuild | Touch build | Str |  | 2025.31550 |
| Saved | Saved | Str |  | 2026-10-26 17:01 |

### Effectors

| name | label | style | default | value |
|---|---|---|---|---|
| Effon | Effectors on (/project1/effectors) | Toggle | False | False |
| Effselect | Use effectors (all / names / #tags) | StrMenu | all | all |
| Effgain | Weight gain | Float | 1.0 | 1.0 |
| Effcombine | Combine | Menu | max | max |
| Effradscale | Radius scale | Float | 1.0 | 1.0 |
| Effragged | Ragged edge | Float | 0.0 | 0.0 |
| Effraggedfreq | Ragged freq | Float | 4.0 | 4.0 |
| Effoverride | Own falloff (ignore per-effector) | Toggle | False | False |
| Effradius | Own radius | Float | 0.5 | 0.5 |
| Effexp | Own exponent | Float | 1.0 | 1.0 |
| Effshape | Own shape | Menu | smooth | smooth |
| Effcentrex | Plane centre (world) | XYZW | 0.0 | 0.0 |
| Effcentrey | Plane centre (world) | XYZW | 0.0 | 0.0 |
| Effcentrez | Plane centre (world) | XYZW | 0.0 | 0.0 |
| Effplanew | Plane width (world) | Float | 1.125 | 1.125 |
| Effplaneh | Plane height (world) | Float | 2.0 | 2.0 |
| Effpush | Push (outward) | Float | 1.0 | 1.0 |
| Effswirl | Swirl | Float | 0.0 | 0.0 |
| Effwake | Wake (effector velocity) | Float | 1.0 | 1.0 |
| Effdye | Dye amount | Float | 1.0 | 1.0 |
| Effcolourr | Dye colour | RGBA | 1.0 | 1.0 |
| Effcolourg | Dye colour | RGBA | 0.45 | 0.45 |
| Effcolourb | Dye colour | RGBA | 0.1 | 0.1 |

## Perf

cook 1.175 ms (CPU 1.175 / GPU 1.786) summed over the 16 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BN_fluid2d", "parent": "/project1/lab"}` (lands parked)
