# POP_crack3d

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:09 from `/project1/lab/POP_crack3d`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Crack

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Style | Style | Menu | lit | lit |
| Cellscale | Cells per object unit | Float | 4.0 | 4.0 |
| Width | Crack width (F2 - F1, cell units) | Float | 0.05 | 0.05 |
| Progress | Crack front progress | Float | 1.0 | 1.0 |
| Auto | Auto progress (loops 0..1) | Toggle | False | False |
| Autospeed | Auto speed (per s) | Float | 0.25 | 0.25 |
| Reach | Reach at progress 1 (object units) | Float | 2.5 | 2.5 |
| Soft | Front softness | Float | 0.05 | 0.05 |
| Impactx | Impact x (object space) | Float | 0.0 | 0.0 |
| Impacty | Impact y | Float | 0.0 | 0.0 |
| Impactz | Impact z | Float | 1.0 | 1.0 |
| Erode | Erode (fraction of reached cells removed) | Float | 0.0 | 0.0 |
| Seed | Seed | Int | 1 | 1 |
| Glow | Crack glow intensity | Float | 2.0 | 2.0 |
| Basemode | Basemode | Menu | flat | flat |
| Glowcolorr | Crack glow colour | RGBA | 1.0 | 1.0 |
| Glowcolorg | Crack glow colour | RGBA | 0.55 | 0.55 |
| Glowcolorb | Crack glow colour | RGBA | 0.15 | 0.15 |
| Basecolorr | Base colour | RGBA | 0.12 | 0.12 |
| Basecolorg | Base colour | RGBA | 0.12 | 0.12 |
| Basecolorb | Base colour | RGBA | 0.14 | 0.14 |

### Object

| name | label | style | default | value |
|---|---|---|---|---|
| Shape | Shape | Menu | sphere | sphere |
| Custompop | Custom POP path (Shape custom) | Str |  |  |
| Detail | Sphere geodesic freq | Int | 24 | 24 |
| Tilt | Tilt deg (x) | Float | 15.0 | 15.0 |
| Orbit | Orbit deg (y) | Float | 0.0 | 0.0 |
| Spin | Spin deg / s (y) | Float | 10.0 | 10.0 |
| Dist | Camera distance | Float | 4.0 | 4.0 |
| Fov | Vertical fov | Float | 40.0 | 40.0 |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Resw | Output width | Int | 1080 | 1080 |
| Resh | Output height | Int | 1920 | 1920 |

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
| Zkm1 | Cracks | Float | 0.0 | 0.5 |
| Zkm2 | Speed | Float | 0.0 | 0.5 |
| Zkm3 | Zoom | Float | 0.0 | 0.5 |

## Perf

cook 43.669 ms (CPU 43.669 / GPU 1.903) summed over the 4 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_crack3d", "parent": "/project1/lab"}` (lands parked)
