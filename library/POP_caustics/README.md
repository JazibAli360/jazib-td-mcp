# POP_caustics

v0.1.2 - TD 2025.31550 - exported 2026-10-29 00:09:06 from `/project1/lab/POP_caustics`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 256x256

## Custom parameters

### Caustics

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Refractor | Refractor | Menu | water | water |
| Ior | Index of refraction | Float | 1.33 | 1.33 |
| Lightangle | Light tilt deg (about y) | Float | 0.0 | 0.0 |
| Speed | Speed (water time / s) | Float | 1.0 | 1.0 |
| Amp | Water amplitude | Float | 0.02 | 0.02 |
| Freq | Water frequency | Float | 6.0 | 6.0 |
| Radius | Sphere radius | Float | 0.5 | 0.5 |
| Thickness | Slab thickness x in1 luma | Float | 0.1 | 0.1 |
| Direct | Rays that miss the sphere still light the floor | Toggle | True | True |

### Rays

| name | label | style | default | value |
|---|---|---|---|---|
| Rays | Rays per side (count = Rays^2, cap 1M) | Int | 256 | 256 |
| Simres | Floor texels per side (0 = Rays) | Int | 0 | 0 |
| Lightsize | Light square size (world) | Float | 2.0 | 2.0 |
| Floorsize | Floor square shown (world) | Float | 2.0 | 2.0 |
| Floordepth | Floor depth below the surface / centre | Float | 1.0 | 1.0 |
| Size | Point size px (1 = exact sums) | Float | 1.0 | 1.0 |
| Jitter | Ray jitter in its cell (hashed per frame, 0 = grid) | Float | 1.0 | 1.0 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Exposure | Exposure | Float | 0.5 | 0.5 |
| Persist | Persist (long exposure) | Float | 0.0 | 0.0 |
| Composite | Composite | Menu | alone | alone |
| Tintr | Tint red | Float | 0.75 | 0.75 |
| Tintg | Tint green | Float | 0.95 | 0.95 |
| Tintb | Tint blue | Float | 1.0 | 1.0 |

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
| Zkm1 | Waves | Float | 0.0 | 0.5 |
| Zkm2 | Focus | Float | 0.0 | 0.5 |

## Perf

cook 1.28 ms (CPU 1.28 / GPU 1.438) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_caustics", "parent": "/project1/lab"}` (lands parked)
