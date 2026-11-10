# POP_tubes

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:20 from `/project1/lab/POP_tubes`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 64x64

## Custom parameters

### Tubes

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Route | Route | Menu | tubes | tubes |
| Source | Source | Menu | lissajous | lissajous |
| Play | Play | Toggle | True | True |
| Reset | Reset trails | Pulse | False | False |
| Speed | Speed | Float | 1.0 | 1.0 |
| Scale | Path scale | Float | 0.6 | 0.6 |
| Seed | Seed | Int | 1 | 1 |
| Tracks | Tracks | Int | 64 | 64 |
| Samples | Samples per trail | Int | 64 | 64 |
| Sides | Tube sides | Int | 8 | 8 |
| Radius | Tube radius at the head | Float | 0.012 | 0.012 |
| Taper | Taper exponent | Float | 1.0 | 1.0 |
| Resetat | internal: frame of the last Reset | Float | -100.0 | 221211.0 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Palette | Palette | Menu | neon | neon |
| Fade | Fade along the trail (exponent) | Float | 1.5 | 1.5 |
| Gain | Gain | Float | 1.0 | 1.0 |
| Halo | Halo (render mips, no Bloom TOP) | Float | 0.6 | 0.6 |
| Spin | Spin deg / s | Float | 6.0 | 6.0 |
| Dist | Camera distance | Float | 2.4 | 2.4 |
| Zoom | Zoom | Float | 1.0 | 1.0 |
| Msaa | Render MSAA (1x saves ~0.6 ms GPU, aliased tube edges) | Menu | aa4 | aa4 |

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
| Zkm1 | Energy | Float | 0.0 | 0.5 |
| Zkm2 | Glow | Float | 0.0 | 0.5 |
| Zkm3 | Thick | Float | 0.0 | 0.5 |

## Perf

cook 0.948 ms (CPU 0.948 / GPU 3.135) summed over the 9 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_tubes", "parent": "/project1/lab"}` (lands parked)
