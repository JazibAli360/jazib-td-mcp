# POP_fillbody

v0.1.2 - TD 2025.31550 - exported 2026-10-29 00:09:10 from `/project1/lab/POP_fillbody`

## Inputs / outputs

- in `caps_in` (inCHOP)
- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Fillbody

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Count | Particles | Int | 16384 | 16384 |
| Speed | Speed | Float | 1.0 | 1.0 |
| Substeps | Substeps | Int | 2 | 2 |
| Wander | Wander force | Float | 1.5 | 1.5 |
| Wanderfreq | Wander frequency | Float | 6.0 | 6.0 |
| Damp | Damping | Float | 2.0 | 2.0 |
| Margin | Keep this far inside the skin | Float | 0.004 | 0.004 |
| Respawn | Respawn per second (fraction) | Float | 0.02 | 0.02 |
| Seed | Seed | Int | 1 | 1 |
| Reset | Reset (spawn inside again) | Pulse | False | False |

### Body

| name | label | style | default | value |
|---|---|---|---|---|
| Bodysrc | Bodysrc | Menu | dancer | dancer |
| Dancespeed | Dance speed (0 = frozen pose) | Float | 0.5 | 0.5 |
| Posetime | Pose time offset s | Float | 0.0 | 0.0 |
| Pose | Pose amount (0 = standing) | Float | 1.0 | 1.0 |
| Bodyx | Body x | Float | 0.0 | 0.0 |
| Bodyy | Body y | Float | 0.04 | 0.04 |
| Bodyz | Body z | Float | 0.0 | 0.0 |
| Bodyscale | Body scale | Float | 0.9 | 0.9 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Size | Point size px | Float | 2.0 | 2.0 |
| Bright | Brightness | Float | 0.6 | 0.6 |
| Hue1 | Hue slow | Float | 0.55 | 0.55 |
| Hue2 | Hue fast | Float | 0.95 | 0.95 |
| Sat | Saturation | Float | 0.7 | 0.7 |
| Colorspeed | Speed for the fast hue (1 / units per s) | Float | 2.0 | 2.0 |
| Gain | Render gain | Float | 1.0 | 1.0 |
| Persist | Trails (0 = none) | Float | 0.0 | 0.0 |
| Tilt | Tilt deg (x) | Float | 0.0 | 0.0 |
| Orbit | Orbit deg (y) | Float | 0.0 | 0.0 |
| Dist | Camera distance | Float | 1.2 | 1.2 |
| Zoom | Zoom (1 = 1 unit tall frame at z 0) | Float | 1.0 | 1.0 |

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
| Zkm3 | Pose | Float | 0.0 | 0.5 |

## Perf

cook 0.977 ms (CPU 0.977 / GPU 2.914) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_fillbody", "parent": "/project1/lab"}` (lands parked)
