# GN_reaction_diffusion

> reaction_diffusion: GN_reaction_diffusion Gray-Scott COMP (live-verified v1 on 2025.31550, 26 Oct 2026, T-108)

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:08:56 from `/project1/lab/GN_reaction_diffusion`

`/project1/lab/GN_reaction_diffusion`. Gray-Scott reaction-diffusion with every pass written as a **compute** GLSL TOP
(T-46/T-47), the step pass running `npasses = Steps` (T-91 (3)). Research: `docs/research/O_generative_simulations.md`
4.2, `BN_fluid_cloth_sims.md` 5.9 (Karl Sims' scheme: 3x3 Laplacian centre -1 / edges 0.2 / diagonals 0.05,
DA 1, DB 0.5, dt 1). **No limits** (user rule): open ranges, nothing clamps the look.

Build doc: `docs/builds/reaction_diffusion.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- in `in3` (inTOP) 128x128
- in `in4` (inTOP) 128x128
- in `in5` (inCHOP)
- in `in6` (inCHOP)
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 252x448

## Custom parameters

### Sim

| name | label | style | default | value |
|---|---|---|---|---|
| Simh | Sim cells (height) | Int | 448 | 448 |
| Resw | Out width | Int | 1080 | 1080 |
| Resh | Out height | Int | 1920 | 1920 |
| Steps | Steps per frame | Int | 8 | 8 |
| Dt | Dt per step | Float | 1.0 | 1.0 |
| Da | Diffusion A | Float | 1.0 | 1.0 |
| Db | Diffusion B | Float | 0.5 | 0.44 |
| Edge | Edges | Menu | wrap | wrap |
| Clampstate | Clamp A/B to 0..1 | Toggle | True | True |
| Feedoff | Feed offset | Float | 0.0 | 0.0 |
| Killoff | Kill offset | Float | 0.0 | 0.0 |
| Fusesteps | Fuse steps (8 per dispatch) | Toggle | True | True |

### Preset

| name | label | style | default | value |
|---|---|---|---|---|
| Preseta | Preset A | Menu | coral | coral |
| Presetb | Preset B | Menu | mitosis | mitosis |
| Morph | Morph A -> B | Float | 0.0 | 0.0 |
| Morphgo | Morph go (A <-> B) | Pulse | False | False |
| Morphtime | Morph go time s | Float | 4.0 | 4.0 |
| Morphlfo | Morph LFO | Menu | off | off |
| Morphrate | LFO rate Hz | Float | 0.05 | 0.05 |
| Morphdepth | LFO depth | Float | 0.0 | 0.0 |
| Mapmode | Morph map | Menu | none | none |
| Mapamt | Map amount | Float | 0.5 | 0.5 |
| Mapscale | Map noise scale | Float | 3.0 | 3.0 |
| Mapimg | Morph from in4 TOP | Float | 0.0 | 0.0 |
| Fmin | Pearson f min | Float | 0.01 | 0.01 |
| Fmax | Pearson f max | Float | 0.09 | 0.09 |
| Kmin | Pearson k min | Float | 0.045 | 0.045 |
| Kmax | Pearson k max | Float | 0.07 | 0.07 |
| Customf | Custom f | Float | 0.055 | 0.055 |
| Customk | Custom k | Float | 0.062 | 0.062 |

### Seed

| name | label | style | default | value |
|---|---|---|---|---|
| Seedmode | Seed on reset | Menu | spots | spots |
| Seedsize | Seed size (heights) | Float | 0.04 | 0.04 |
| Seedcount | Spot count | Int | 24 | 24 |
| Seeddensity | Noise density | Float | 0.05 | 0.05 |
| Seed | Seed | Int | 1 | 1 |
| Seedtext | Seed text | Str | PRISM | PRISM |
| Textsize | Text size (heights) | Float | 0.12 | 0.12 |
| Inject | Continuous inject (in1 / text) | Float | 0.0 | 0.0 |
| Injectsrc | Inject source | Menu | image | image |
| Reseed | Reseed (new seed + reset) | Pulse | False | False |
| Reset | Reset | Pulse | False | False |

### Flow

| name | label | style | default | value |
|---|---|---|---|---|
| Anisomode | Anisotropy | Menu | off | off |
| Aniso | Anisotropy amount | Float | 0.6 | 0.6 |
| Anisoangle | Angle deg | Float | 0.0 | 0.0 |
| Anisoscale | Noise field scale | Float | 2.0 | 2.0 |
| Flowmode | Flow advection | Menu | off | off |
| Flowgain | Flow gain | Float | 0.3 | 0.3 |
| Flowx | Drift x (cells/step) | Float | 0.0 | 0.0 |
| Flowy | Drift y (cells/step) | Float | 0.1 | 0.1 |
| Flowscale | Curl noise scale | Float | 3.0 | 3.0 |
| Flowspeed | Curl noise speed | Float | 0.1 | 0.1 |

### Inject

| name | label | style | default | value |
|---|---|---|---|---|
| Effon | Effectors on | Toggle | True | True |
| Effectors | Effector Nulls (names/paths/patterns) | StrMenu | eff* | eff* |
| Planeh | Plane height (world units) | Float | 1.0 | 1.0 |
| Effradius | Effector radius | Float | 0.08 | 0.08 |
| Effstrength | Effector inject (- erases) | Float | 0.05 | 0.05 |
| Effmorph | Effector morph | Float | 0.0 | 0.0 |
| Efffalloff | Effector falloff | Menu | gauss | gauss |
| Morphdecay | Morph memory (0 = none) | Float | 0.0 | 0.0 |
| Maskthresh | Mask threshold (in2) | Float | 0.5 | 0.5 |
| Pointradius | in5 point radius | Float | 0.03 | 0.03 |
| Mousemode | Mouse | Menu | off | off |
| Mouseradius | Mouse radius | Float | 0.03 | 0.03 |
| Mousestrength | Mouse inject | Float | 1.0 | 1.0 |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiomode | Audio (in6) | Menu | off | off |
| Audiogain | Audio gain | Float | 4.0 | 4.0 |
| Lowhz | Low band Hz | Float | 150.0 | 150.0 |
| Kickthresh | Kick threshold | Float | 0.3 | 0.3 |
| Refractory | Kick refractory s | Float | 0.15 | 0.15 |
| Audiomorph | Level -> morph | Float | 0.5 | 0.5 |
| Burst | Burst | Pulse | False | False |
| Burstpattern | Burst pattern | Menu | random | random |
| Burstcount | Burst spots | Int | 3 | 3 |
| Burstradius | Burst radius | Float | 0.04 | 0.04 |
| Burststrength | Burst inject | Float | 1.0 | 1.0 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Valuemode | Value | Menu | b | b |
| Lo | Value low | Float | 0.0 | 0.0 |
| Hi | Value high | Float | 0.35 | 0.35 |
| Colormode | Colour | Menu | palette | palette |
| Palette | Palette | Menu | prism | prism |
| Ramptop | Ramp TOP (empty = inner ramp) | TOP |  |  |
| Invert | Invert value | Toggle | False | False |
| Shade | Emboss shade | Float | 0.0 | 0.0 |
| Shadeheight | Emboss height | Float | 1.0 | 1.0 |
| Lightangle | Light angle deg | Float | 135.0 | 135.0 |
| Edgeglow | Edge glow | Float | 0.0 | 0.0 |
| Edgecolorr | Edge colour | RGBA | 1.0 | 1.0 |
| Edgecolorg | Edge colour | RGBA | 0.9 | 0.9 |
| Edgecolorb | Edge colour | RGBA | 0.7 | 0.7 |
| Exposure | Exposure (stops) | Float | 0.0 | 0.0 |
| Gamma | Gamma | Float | 1.0 | 1.0 |
| Alpha | Alpha | Menu | opaque | opaque |
| Premult | Premultiplied | Toggle | True | True |
| Showeff | Preview gizmos | Toggle | True | True |
| Pal1r | Palette 1 (low) | RGBA | 0.02 | 0.02 |
| Pal1g | Palette 1 (low) | RGBA | 0.0 | 0.0 |
| Pal1b | Palette 1 (low) | RGBA | 0.06 | 0.06 |
| Pal2r | Palette 2 | RGBA | 0.25 | 0.25 |
| Pal2g | Palette 2 | RGBA | 0.05 | 0.05 |
| Pal2b | Palette 2 | RGBA | 0.55 | 0.55 |
| Pal3r | Palette 3 | RGBA | 0.85 | 0.85 |
| Pal3g | Palette 3 | RGBA | 0.15 | 0.15 |
| Pal3b | Palette 3 | RGBA | 0.65 | 0.65 |
| Pal4r | Palette 4 | RGBA | 1.0 | 1.0 |
| Pal4g | Palette 4 | RGBA | 0.55 | 0.55 |
| Pal4b | Palette 4 | RGBA | 0.3 | 0.3 |
| Pal5r | Palette 5 (high) | RGBA | 1.0 | 1.0 |
| Pal5g | Palette 5 (high) | RGBA | 0.95 | 0.95 |
| Pal5b | Palette 5 (high) | RGBA | 0.85 | 0.85 |

### Control

| name | label | style | default | value |
|---|---|---|---|---|
| Pause | Pause | Toggle | False | False |
| Step | Step (while paused) | Pulse | False | False |
| Stopat | Pause at step (0 = off) | Int | 0 | 0 |
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
| Zkm1 | Speed | Float | 0.0 | 0.5 |
| Zkm2 | Mutate | Float | 0.0 | 0.5 |
| Zkm3 | Light | Float | 0.0 | 0.5 |

## Perf

cook 1.077 ms (CPU 1.077 / GPU 1.971) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GN_reaction_diffusion", "parent": "/project1/lab"}` (lands parked)
