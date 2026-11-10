# ZK_controls_kit

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:32 from `/project1/lab/ZK_controls_kit`

## Inputs / outputs

- out `out1` (outTOP) 1080x1920

## Custom parameters

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Period | Period | Float | 1.2 | 6.52046 |
| Harmonics | Harmonics | Int | 3 | 8 |
| Gain | Gain | Float | 0.0 | -0.768156 |
| Exponent | Exponent | Float | 1.0 | 2.45445 |
| Noisetype | Type | Menu | simplex3d | simplex3d |
| Mono | Mono | Toggle | False | True |
| Tintr | Tint | RGBA | 0.91 | 0.656183 |
| Tintg | Tint | RGBA | 0.27 | 0.950673 |
| Tintb | Tint | RGBA | 0.11 | 0.492735 |
| Speed | Speed | Float | 0.3 | 2.5772399999999998 |
| Demores | Noise res | Menu | half | half |

### Motion

| name | label | style | default | value |
|---|---|---|---|---|
| Offset1 | Offset | Float | 0.0 | 0.0 |
| Offset2 | Offset | Float | 0.0 | 0.0 |
| Rotate | Rotate | Float | 0.0 | -113.703 |
| Flash | Flash | Momentary | False | False |
| Reseed | Reseed | Pulse | False | False |
| Caption | Caption | Str | zkit demo | zkit demo |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 1.0 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Detail | Float | 0.0 | 0.5 |
| Zkm2 | Energy | Float | 0.0 | 0.5 |

## Perf

cook 49.277 ms (CPU 49.277 / GPU 1.181) summed over the 5 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "ZK_controls_kit", "parent": "/project1/lab"}` (lands parked)
