# LK_spectrum_glass

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:59 from `/project1/lab/LK_spectrum_glass`

## Inputs / outputs

- in `audio_in` (inCHOP)
- in `spec_in_t` (inTOP) 128x128
- out `look_out` (outTOP) 1920x1080

## Custom parameters

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Barcount | Bar count | Int | 32 | 56 |
| Ringsize | Ring size | Float | 0.18 | 0.181 |
| Ringreact | Ring reaction | Float | 0.08 | 0.186 |
| Kickglow | Kick glow (flash-safe) | Float | 0.08 | 0.08 |
| Spin | Ring spin | Float | 0.02 | 0.106 |
| React | Reactivity | Float | 1.0 | 0.937838 |
| Opencontrols | Open controls window | Pulse | False | False |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Colorar | Colour A | RGBA | 0.55 | 0.55 |
| Colorag | Colour A | RGBA | 0.2 | 0.2 |
| Colorab | Colour A | RGBA | 0.85 | 0.85 |
| Colorbr | Colour B | RGBA | 1.0 | 1.0 |
| Colorbg | Colour B | RGBA | 0.55 | 0.55 |
| Colorbb | Colour B | RGBA | 0.25 | 0.25 |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |

## Perf

cook 0.131 ms (CPU 0.131 / GPU 0.845) summed over the 3 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "LK_spectrum_glass", "parent": "/project1/lab"}` (lands parked)
