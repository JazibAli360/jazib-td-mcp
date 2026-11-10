# POP_tree

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:19 from `/project1/lab/POP_tree`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 92x46

## Custom parameters

### Tree

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Branches | Branches per node | Int | 2 | 2 |
| Depth | Depth (branchings; capped so segments <= 262k) | Int | 10 | 10 |
| Spread | Spread deg | Float | 30.0 | 30.0 |
| Twist | Twist deg per level (phyllotaxis) | Float | 137.5 | 137.5 |
| Jitter | Angle jitter deg (per node) | Float | 8.0 | 8.0 |
| Ratio | Length ratio per level | Float | 0.72 | 0.72 |
| Length | Trunk length | Float | 0.35 | 0.35 |
| Lenjitter | Length jitter (per node) | Float | 0.15 | 0.15 |
| Progress | Growth (outward by level) | Float | 1.0 | 1.0 |
| Seed | Seed | Int | 1 | 1 |

### Wind

| name | label | style | default | value |
|---|---|---|---|---|
| Speed | Clock speed | Float | 1.0 | 1.0 |
| Sway | Sway deg (grows with level) | Float | 6.0 | 6.0 |
| Swayspeed | Sway rad / s | Float | 1.5 | 1.5 |

### Draw

| name | label | style | default | value |
|---|---|---|---|---|
| Samples | Dust points per segment (total capped at 1M) | Int | 8 | 8 |
| Pointsize | Point size px | Float | 1.0 | 1.0 |
| Lines | Draw lines instead of dust (LIVE CHECK gated) | Toggle | False | False |
| Hue0 | Hue at the root | Float | 0.08 | 0.08 |
| Hue1 | Hue at the tips | Float | 0.35 | 0.35 |
| Sat | Saturation | Float | 0.7 | 0.7 |
| Bright | Brightness | Float | 1.0 | 1.0 |
| Gain | Gain per point (additive) | Float | 0.35 | 0.35 |
| Width | Width (stored for consumers) | Float | 1.0 | 1.0 |
| Widthratio | Width ratio per level | Float | 0.75 | 0.75 |
| Composite | Composite | Menu | alone | alone |

### View

| name | label | style | default | value |
|---|---|---|---|---|
| Dist | Camera distance | Float | 3.0 | 3.0 |
| Camheight | Camera height | Float | 1.0 | 1.0 |
| Fov | Vertical fov deg | Float | 45.0 | 45.0 |
| Orbit | Orbit deg | Float | 0.0 | 0.0 |
| Spin | Spin deg / s | Float | 10.0 | 10.0 |

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
| Zkm1 | Chaos | Float | 0.0 | 0.5 |
| Zkm2 | Wind | Float | 0.0 | 0.5 |
| Zkm3 | Glow | Float | 0.0 | 0.5 |

## Perf

cook 1.205 ms (CPU 1.205 / GPU 1.932) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_tree", "parent": "/project1/lab"}` (lands parked)
