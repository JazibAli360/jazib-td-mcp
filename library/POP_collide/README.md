# POP_collide

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:07 from `/project1/lab/POP_collide`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Collide

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount (0 = in1 untouched) | Float | 1.0 | 1.0 |
| Count | Particles | Int | 16384 | 16384 |
| Speed | Speed (sim seconds per second at 60 fps) | Float | 1.0 | 1.0 |
| Substeps | Substeps | Int | 2 | 2 |
| Gravity | Gravity (units / s2) | Float | -0.8 | -0.8 |
| Drag | Drag | Float | 0.1 | 0.1 |
| Wind | Wind (value noise) | Float | 0.2 | 0.2 |
| Windfreq | Wind frequency | Float | 3.0 | 3.0 |
| Restitution | Restitution (bounce) | Float | 0.5 | 0.5 |
| Friction | Friction (tangential loss) | Float | 0.1 | 0.1 |
| Seed | Seed | Int | 1 | 1 |
| Reset | Reset | Pulse | False | False |
| Testmode | Test mode (one particle, no wind / drag) | Toggle | False | False |
| Testh | Test particle start y | Float | 0.4 | 0.4 |

### Emitter

| name | label | style | default | value |
|---|---|---|---|---|
| Emitshape | Emitshape | Menu | line | line |
| Emitx | Emitter x | Float | 0.0 | 0.14 |
| Emity | Emitter y | Float | 0.48 | 0.48 |
| Emitz | Emitter z | Float | 0.0 | 0.0 |
| Emitsize | Emitter size | Float | 0.25 | 0.25 |
| Emitvx | Start velocity x | Float | 0.0 | 0.0 |
| Emitvy | Start velocity y | Float | -0.1 | -0.1 |
| Emitvz | Start velocity z | Float | 0.0 | 0.0 |
| Spread | Velocity spread | Float | 0.05 | 0.05 |
| Life | Life s (x 0.5..1.5) | Float | 6.0 | 6.0 |

### Colliders

| name | label | style | default | value |
|---|---|---|---|---|
| Floor | Floor on | Toggle | True | True |
| Floory | Floor y | Float | -0.45 | -0.45 |
| Sphere1on | Sphere 1 on | Toggle | True | True |
| Sphere1x | Sphere 1 x | Float | 0.0 | 0.0 |
| Sphere1y | Sphere 1 y | Float | -0.1 | -0.1 |
| Sphere1z | Sphere 1 z | Float | 0.0 | 0.0 |
| Sphere1r | Sphere 1 radius | Float | 0.12 | 0.12 |
| Sphere2on | Sphere 2 on | Toggle | True | True |
| Sphere2x | Sphere 2 x | Float | 0.12 | 0.12 |
| Sphere2y | Sphere 2 y | Float | 0.15 | 0.15 |
| Sphere2z | Sphere 2 z | Float | 0.0 | 0.0 |
| Sphere2r | Sphere 2 radius | Float | 0.07 | 0.07 |
| Sphere3on | Sphere 3 on | Toggle | False | False |
| Sphere3x | Sphere 3 x | Float | 0.0 | 0.0 |
| Sphere3y | Sphere 3 y | Float | 0.0 | 0.0 |
| Sphere3z | Sphere 3 z | Float | 0.0 | 0.0 |
| Sphere3r | Sphere 3 radius | Float | 0.1 | 0.1 |
| Sphere4on | Sphere 4 on | Toggle | False | False |
| Sphere4x | Sphere 4 x | Float | 0.0 | 0.0 |
| Sphere4y | Sphere 4 y | Float | 0.0 | 0.0 |
| Sphere4z | Sphere 4 z | Float | 0.0 | 0.0 |
| Sphere4r | Sphere 4 radius | Float | 0.1 | 0.1 |
| Box1on | Box 1 on | Toggle | True | True |
| Box1x | Box 1 centre x | Float | -0.12 | -0.12 |
| Box1y | Box 1 centre y | Float | -0.3 | -0.3 |
| Box1z | Box 1 centre z | Float | 0.0 | 0.0 |
| Box1hx | Box 1 half size x | Float | 0.08 | 0.08 |
| Box1hy | Box 1 half size y | Float | 0.03 | 0.03 |
| Box1hz | Box 1 half size z | Float | 0.2 | 0.2 |
| Box2on | Box 2 on | Toggle | False | False |
| Box2x | Box 2 centre x | Float | 0.0 | 0.0 |
| Box2y | Box 2 centre y | Float | 0.0 | 0.0 |
| Box2z | Box 2 centre z | Float | 0.0 | 0.0 |
| Box2hx | Box 2 half size x | Float | 0.1 | 0.1 |
| Box2hy | Box 2 half size y | Float | 0.1 | 0.1 |
| Box2hz | Box 2 half size z | Float | 0.1 | 0.1 |

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
| Zkm2 | Chaos | Float | 0.0 | 0.25 |
| Zkm3 | Glow | Float | 0.0 | 0.5 |

## Perf

cook 1.828 ms (CPU 1.828 / GPU 1.776) summed over the 9 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "POP_collide", "parent": "/project1/lab"}` (lands parked)
