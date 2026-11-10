# POP_branching

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:04 from `/project1/lab/POP_branching`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Branching

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Play | Play (off = hold) | Toggle | True | True |
| Reset | Reset (reseed, clear trail) | Pulse | False | False |
| Seedmode | Seedmode | Menu | center | center |
| Seedcount | Seed tips | Int | 8 | 8 |
| Maxtips | Max tips | Int | 256 | 256 |
| Step | Step px / frame | Float | 1.0 | 1.0 |
| Sensorangle | Sensor angle deg | Float | 30.0 | 30.0 |
| Sensordist | Sensor distance px | Float | 6.0 | 6.0 |
| Turn | Turn deg | Float | 20.0 | 20.0 |
| Wander | Wander deg | Float | 10.0 | 10.0 |
| Killthresh | Die when trail ahead > | Float | 2.0 | 2.0 |
| Splitrate | Split chance / frame | Float | 0.02 | 0.02 |
| Splitangle | Split angle deg | Float | 25.0 | 25.0 |
| Maxage | Max age (frames) | Int | 600 | 600 |
| Deposit | Deposit | Float | 1.0 | 1.0 |
| Decay | Trail decay / frame | Float | 0.995 | 0.995 |
| Diffuse | Trail diffuse (wrap 3x3) | Float | 0.0 | 0.0 |
| Simw | Sim width | Int | 540 | 540 |
| Simh | Sim height | Int | 960 | 960 |
| Seed | Seed | Int | 1 | 1 |
| Resetat | Reset frame (internal, set by Reset) | Int | -10 | 87303 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Huea | Hue (young) | Float | 0.08 | 0.08 |
| Hueb | Hue (old) | Float | 0.6 | 0.6 |
| Sat | Saturation | Float | 0.8 | 0.8 |
| Gain | Gain | Float | 1.0 | 1.0 |

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
| Zkm2 | Growth | Float | 0.0 | 0.5 |
| Zkm3 | Glow | Float | 0.0 | 0.5 |

## Perf

cook 0.342 ms (CPU 0.342 / GPU 1.323) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_branching", "parent": "/project1/lab"}` (lands parked)
