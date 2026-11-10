# POP_linegrowth

v0.1.2 - TD 2025.31550 - exported 2026-10-29 00:09:11 from `/project1/lab/POP_linegrowth`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Growth

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Play | Play (off = hold) | Toggle | True | True |
| Reset | Reset (reseed) | Pulse | False | False |
| Shape | Shape | Menu | circle | circle |
| Seedcount | Seed nodes | Int | 64 | 64 |
| Seedradius | Seed radius (frame heights) | Float | 0.1 | 0.1 |
| Sides | Polygon sides | Int | 5 | 5 |
| Maxnodes | Max nodes (growth stops here) | Int | 1024 | 1024 |
| Rest | Rest length | Float | 0.006 | 0.006 |
| Maxedge | Split edges longer than | Float | 0.009 | 0.009 |
| Radius | Repulsion radius | Float | 0.02 | 0.02 |
| Spring | Spring | Float | 0.5 | 0.5 |
| Align | Align (smooth) | Float | 0.2 | 0.2 |
| Repel | Repel | Float | 0.02 | 0.02 |
| Jitter | Jitter (x rest) | Float | 0.1 | 0.1 |
| Dt | Step | Float | 0.5 | 0.5 |
| Maxstep | Max move per frame | Float | 0.003 | 0.003 |
| Bound | Boundary circle radius | Float | 0.45 | 0.45 |
| Boundk | Boundary push | Float | 1.0 | 1.0 |
| Seed | Seed | Int | 1 | 1 |
| Resetat | Reset frame (internal, set by Reset) | Int | -10 | -10 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Lines | Linestrip view (LIVE CHECK gated; off = points) | Toggle | False | False |
| Size | Point size px | Float | 2.0 | 2.0 |
| Zoom | Zoom | Float | 1.0 | 1.0 |
| Hue | Hue | Float | 0.55 | 0.55 |
| Huespread | Hue along the line | Float | 0.3 | 0.3 |
| Sat | Saturation | Float | 0.8 | 0.8 |
| Gain | Gain | Float | 1.5 | 1.5 |
| Raster | Raster | Menu | compute | compute |

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
| Zkm2 | Speed | Float | 0.0 | 0.5 |
| Zkm3 | Glow | Float | 0.0 | 0.5 |

## Perf

cook 0.303 ms (CPU 0.303 / GPU 1.811) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_linegrowth", "parent": "/project1/lab"}` (lands parked)
