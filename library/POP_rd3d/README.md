# POP_rd3d

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:16 from `/project1/lab/POP_rd3d`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 256x256

## Custom parameters

### Rd3d

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Preset | Preset | Menu | coral | coral |
| Customf | Custom feed | Float | 0.0545 | 0.0545 |
| Customk | Custom kill | Float | 0.062 | 0.062 |
| Play | Play | Toggle | True | True |
| Steps | Steps | Menu | 4 | 4 |
| Stopat | Stop after N steps (-1 = run) | Int | -1 | -1 |
| Reseed | Reseed | Pulse | False | False |
| Seed | Seed | Int | 1 | 1 |
| Density | Seed spot density | Float | 0.35 | 0.35 |
| Spotsize | Seed spot radius (cells) | Float | 0.3 | 0.3 |
| Simres | Sim resolution (square, wraps) | Int | 256 | 256 |
| Resetat | internal: frame of the last Reseed | Float | -100.0 | 256433.0 |

### Surface

| name | label | style | default | value |
|---|---|---|---|---|
| Shape | Shape | Menu | torus | torus |
| Height | Height x V (along the normal) | Float | 0.15 | 0.15 |
| Cols | Mesh columns (u) | Int | 256 | 256 |
| Rows | Mesh rows (v) | Int | 128 | 128 |
| Spin | Spin deg / s (y) | Float | 10.0 | 10.0 |
| Tilt | Tilt deg (x) | Float | 60.0 | 60.0 |
| Dist | Camera distance (5.2 fits the torus in 9:16) | Float | 5.2 | 5.2 |
| Zoom | Zoom | Float | 1.0 | 1.0 |
| Palette | Palette | Menu | bio | bio |
| Light | Lambert amount | Float | 1.0 | 1.0 |
| Rim | Rim light | Float | 0.5 | 0.5 |

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
| Zkm1 | Relief | Float | 0.0 | 0.5 |
| Zkm2 | Turn | Float | 0.0 | 0.5 |

## Perf

cook 37.808 ms (CPU 37.808 / GPU 1.36) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_rd3d", "parent": "/project1/lab"}` (lands parked)
