# POP_meshwarp

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:14 from `/project1/lab/POP_meshwarp`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Meshwarp

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Mode | Mode | Menu | ripple | ripple |
| Strength | Strength | Float | 0.5 | 0.5 |
| Freq | Frequency | Float | 3.0 | 3.0 |
| Speed | Speed (cycles / s) | Float | 0.25 | 0.25 |
| Centerx | Centre u | Float | 0.5 | 0.5 |
| Centery | Centre v | Float | 0.5 | 0.5 |
| Radius | Radius (sheet heights) | Float | 0.5 | 0.5 |
| Depth | Depth (z out of the sheet) | Float | 0.3 | 0.3 |
| Uvwarp | Texture warp | Float | 1.0 | 1.0 |
| Seed | Seed | Int | 1 | 1 |

### Sheet

| name | label | style | default | value |
|---|---|---|---|---|
| Cols | Grid columns | Int | 128 | 128 |
| Rows | Grid rows | Int | 228 | 228 |
| Tilt | Tilt deg (x) | Float | 0.0 | 0.0 |
| Orbit | Orbit deg (y) | Float | 0.0 | 0.0 |
| Roll | Roll deg (z) | Float | 0.0 | 0.0 |
| Dist | Camera distance | Float | 1.2 | 1.2 |
| Zoom | Zoom (1 = sheet fills the frame) | Float | 1.0 | 1.0 |
| Shade | Shading from the bent normal | Float | 0.5 | 0.5 |
| Edge | Edge | Menu | hold | hold |
| Wire | Wireframe (MAT wireframe, 1 px on macOS) | Toggle | False | False |

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
| Zkm1 | Warp | Float | 0.0 | 0.5 |
| Zkm2 | Ripple | Float | 0.0 | 0.5 |
| Zkm3 | Size | Float | 0.0 | 0.5 |

## Perf

cook 45.135 ms (CPU 45.135 / GPU 1.511) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_meshwarp", "parent": "/project1/lab"}` (lands parked)
