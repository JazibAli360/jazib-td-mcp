# FX_haze

> px_haze - volumetric haze, light shafts and bloom v2 (lane W1-D, 27 Oct 2026)

v0.1.0 - TD 2025.31550 - exported 2026-10-27 02:15:32 from `/project1/lab/FX_haze`

User (27 Oct): "volumetric haze nd glow and all", colours changeable, lights placed in 3D affect the scene.
RUBENFRO_COVERAGE rows H1 (depth haze, height falloff, drift), H2 (light shafts), H3 (fog lit around lights), GL1
(bloom: two scales + tint), CO5 (tints). TD target 2025.31550. Phase 1 offline (logic, numpy references, tests,
glslc); **phase 2 live on b5 (27 Oct): every check passed, GPU = numpy reference within float16 (section "Verified
live")**; FX_haze brought home to main /project1/lab/FX_haze (parked).

Build doc: `docs/builds/px_haze.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- out `out1` (outTOP) 128x128

## Custom parameters

### Haze

| name | label | style | default | value |
|---|---|---|---|---|
| Hazeamount | Amount (0 = passthrough) | Float | 1.0 | 1.0 |
| Hazeres | Hazeres | Menu | half | quarter |
| Density | Density | Float | 0.08 | 0.08 |
| Floor | Floor height (y) | Float | 0.0 | 0.0 |
| Falloff | Height falloff | Float | 0.35 | 0.35 |
| Noise | Patchiness (fbm) | Float | 0.5 | 0.5 |
| Noisescale | Noisescale | Float | 0.35 | 0.35 |
| Windx | Drift (units/s) | XYZW | 0.3 | 0.3 |
| Windy | Drift (units/s) | XYZW | 0.05 | 0.05 |
| Windz | Drift (units/s) | XYZW | 0.1 | 0.1 |
| Noisepersample | Noise per sample (detail, slower) | Toggle | False | False |
| Extinction | Extinction (dims the scene) | Float | 1.0 | 1.0 |
| Ambient | Ambient haze | Float | 0.25 | 0.25 |
| Hazecolr | Hazecol | RGBA | 0.55 | 0.55 |
| Hazecolg | Hazecol | RGBA | 0.6 | 0.6 |
| Hazecolb | Hazecol | RGBA | 0.7 | 0.7 |
| Hazecolsrc | Hazecolsrc | Menu | source | source |
| Hazepalpos | Palette position | Float | 0.0 | 0.0 |
| Hazepalspread | Palette spread (x attribute) | Float | 1.0 | 1.0 |
| Hazekeep | Keep source colour | Float | 0.0 | 0.0 |
| Hazetintr | Lit fog tint | RGBA | 1.0 | 1.0 |
| Hazetintg | Lit fog tint | RGBA | 1.0 | 1.0 |
| Hazetintb | Lit fog tint | RGBA | 1.0 | 1.0 |
| Gain | Lit fog gain | Float | 1.0 | 1.0 |
| Anisotropy | Forward scatter (g) | Float | 0.35 | 0.35 |
| Steps | Steps | Int | 10 | 8 |
| Softradius | Light size | Float | 0.05 | 0.05 |
| Jitter | Jitter | Toggle | False | False |
| Depthmode | Depthmode | Menu | none | none |
| Depthscale | Depthscale | Float | 1.0 | 1.0 |
| Objdist | Object distance (no depth) | Float | 6.0 | 6.0 |
| Maxdist | Max distance (sky) | Float | 60.0 | 60.0 |

### Shafts

| name | label | style | default | value |
|---|---|---|---|---|
| Shafts | Shafts (0 = off) | Float | 0.6 | 0.6 |
| Decay | Decay | Float | 0.96 | 0.97 |
| Length | Length | Float | 0.85 | 0.85 |
| Taps | Taps | Int | 20 | 12 |
| Threshold | Bright pixels emit (0 = off) | Float | 0.0 | 0.0 |
| Disc | Source disc | Float | 0.06 | 0.06 |
| Occlusion | Occlusion | Float | 1.0 | 1.0 |
| Shaftlod | Shaft mip (perf) | Float | 1.0 | 1.0 |

### Lights

| name | label | style | default | value |
|---|---|---|---|---|
| Lights | Light COMPs (paths / patterns) | Str |  |  |
| Camera | Camera COMP (empty = manual) | Str |  |  |
| Camposx | Campos | XYZW | 0.0 | 0.0 |
| Camposy | Campos | XYZW | 1.0 | 1.0 |
| Camposz | Campos | XYZW | 8.0 | 8.0 |
| Camtargetx | Camtarget | XYZW | 0.0 | 0.0 |
| Camtargety | Camtarget | XYZW | 1.0 | 1.0 |
| Camtargetz | Camtarget | XYZW | 0.0 | 0.0 |
| Fov | Horizontal FOV | Float | 45.0 | 45.0 |
| Near | Near | Float | 0.1 | 0.1 |
| Far | Far | Float | 1000.0 | 1000.0 |

### Bloom

| name | label | style | default | value |
|---|---|---|---|---|
| Bloom | Bloom (0 = off) | Float | 0.0 | 0.0 |
| Bloomthr | Bloomthr | Float | 0.8 | 1.0 |
| Bloomknee | Bloomknee | Float | 0.0 | 0.0 |
| Bloomwide | Bloomwide | Float | 1.0 | 1.0 |
| Bloomtight | Bloomtight | Float | 0.6 | 0.6 |
| Bloomclamp | Firefly clamp (0 = off) | Float | 0.0 | 0.0 |
| Bloomcolr | Bloomcol | RGBA | 1.0 | 1.0 |
| Bloomcolg | Bloomcol | RGBA | 1.0 | 1.0 |
| Bloomcolb | Bloomcol | RGBA | 1.0 | 1.0 |
| Bloomcolsrc | Bloomcolsrc | Menu | solid | solid |
| Bloompalpos | Palette position | Float | 0.0 | 0.3 |
| Bloompalspread | Palette spread (x attribute) | Float | 1.0 | 1.0 |
| Bloomkeep | Keep source colour | Float | 0.0 | 0.0 |
| Bloomsat | Bloomsat | Float | 1.0 | 1.0 |
| Ring | Ring halo | Float | 0.0 | 0.0 |
| Ringradius | Ringradius | Float | 0.12 | 0.07 |
| Ringwidth | Ringwidth | Float | 0.5 | 0.3 |
| Ringchroma | Ringchroma | Float | 0.0 | 0.2 |

### Palette

| name | label | style | default | value |
|---|---|---|---|---|
| Palsource | Palsource | Menu | neon_trio | neon_trio |
| Palstops | Custom stops (hex hex ...) | Str |  |  |
| Palmode | Palmode | Menu | gradient | gradient |
| Palinterp | Palinterp | Menu | oklab | oklab |
| Palshift | Palshift | Float | 0.0 | 0.0 |

## Perf

cook 9.09 ms (CPU 9.09 / GPU 1.013) summed over the 4 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_haze", "parent": "/project1/lab"}` (lands parked)
