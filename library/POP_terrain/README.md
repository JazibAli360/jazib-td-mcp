# POP_terrain

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:17 from `/project1/lab/POP_terrain`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Terrain

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Style | Style | Menu | shaded | shaded |
| Speed | Fly speed (world units / s) | Float | 2.0 | 2.0 |
| Snap | Snap scroll to the finest cell (no swimming near the camera) | Toggle | True | True |
| Extent | Extent (half size, world units) | Float | 40.0 | 40.0 |
| Lodpow | LOD power (1 = uniform, 3 = very dense near) | Float | 2.0 | 2.0 |
| Freq | Noise frequency (per world unit) | Float | 0.08 | 0.08 |
| Heightscale | Height scale | Float | 6.0 | 6.0 |
| Octaves | Octaves | Int | 5 | 5 |
| Ridge | Ridged noise (1 - \|2n - 1\|) | Toggle | False | False |
| Seed | Seed | Int | 1 | 1 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Contours | Contour lines per Heightscale | Float | 12.0 | 12.0 |
| Fog | Fog density | Float | 0.02 | 0.02 |
| Lowcolorr | Low colour | RGBA | 0.05 | 0.05 |
| Lowcolorg | Low colour | RGBA | 0.1 | 0.1 |
| Lowcolorb | Low colour | RGBA | 0.3 | 0.3 |
| Midcolorr | Mid colour | RGBA | 0.1 | 0.1 |
| Midcolorg | Mid colour | RGBA | 0.6 | 0.6 |
| Midcolorb | Mid colour | RGBA | 0.5 | 0.5 |
| Highcolorr | High colour | RGBA | 1.0 | 1.0 |
| Highcolorg | High colour | RGBA | 0.9 | 0.9 |
| Highcolorb | High colour | RGBA | 0.7 | 0.7 |
| Fogcolorr | Fog colour | RGBA | 0.0 | 0.0 |
| Fogcolorg | Fog colour | RGBA | 0.0 | 0.0 |
| Fogcolorb | Fog colour | RGBA | 0.0 | 0.0 |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Cols | Grid columns | Int | 160 | 160 |
| Rows | Grid rows | Int | 160 | 160 |
| Camh | Camera height | Float | 10.0 | 10.0 |
| Camz | Camera z | Float | 0.0 | 0.0 |
| Pitch | Pitch down (deg) | Float | 25.0 | 25.0 |
| Fov | Vertical fov (deg) | Float | 70.0 | 70.0 |

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
| Zkm2 | Fly | Float | 0.0 | 0.2 |

## Perf

cook 36.364 ms (CPU 36.364 / GPU 0.415) summed over the 5 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_terrain", "parent": "/project1/lab"}` (lands parked)
