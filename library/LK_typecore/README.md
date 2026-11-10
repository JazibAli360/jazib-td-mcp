# LK_typecore

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:37 from `/project1/lab/LK_typecore`

## Inputs / outputs

- out `type_out` (outTOP) 1920x1080

## Custom parameters

### Type

| name | label | style | default | value |
|---|---|---|---|---|
| Word | Word | Str |  | LIVE |
| Glow | Glow strength | Float | 1.6 | 1.6 |
| Sweepsec | Sweep every (s) | Float | 4.0 | 4.0 |
| Fontsize | Font size | Float | 380.0 | 380.0 |
| Opencontrols | Open controls window | Pulse | False | False |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Outliner | Outline colour | RGBA | 0.62 | 0.62 |
| Outlineg | Outline colour | RGBA | 0.28 | 0.28 |
| Outlineb | Outline colour | RGBA | 0.95 | 0.95 |

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

cook 26.613 ms (CPU 26.613 / GPU 0.671) summed over the 3 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "LK_typecore", "parent": "/project1/lab"}` (lands parked)
