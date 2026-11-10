# BN_cloth

> cloth: BN_cloth cloth + jelly COMP (live v1 in main, 26 Oct 2026, TD 2025.31550; jelly fails live, T-87)

v0.2.1 - TD 2025.31550 - exported 2026-10-29 00:08:01 from `/project1/lab/BN_cloth`

`/project1/lab/BN_cloth`. A self-contained cloth sim: a grid of vertices whose state lives in textures and is stepped
by compute-mode GLSL TOPs (T-46/T-47), rendered by displacing a Grid SOP in a GLSL MAT. Spec:
`docs/research/BN_fluid_cloth_sims.md` section 6 (our clean-room design). **No limits** (user rule): open ranges,
no limiter, no warnings. **Status: live v1 in main (26 Oct, 31550; see "Verified live" below: cloth mode verified, jelly mode fails live, T-87).** Lines marked LIVE CHECK were the plan those results answer.

In: `in1` TOP texture, `in2` TOP pin mask (Pins = mask), `in3` CHOP colliders (`x y z r`, one sample per sphere,
fills the free sphere slots), `in4` CHOP wind (`x y z` + optional `strength`, added to the wind), `in5` CHOP audio
(RMS of the first 2 channels; the COMP never touches audio output). Out: `out1` TOP render (Resw x Resh, default
1080x1920), `out2` TOP positions (rgba32float, Gridw x Gridh, xyz + w 1), `out3` CHOP stats (`maxstretch meanstretch
energy nan steps beat burst kicks released`).

Build doc: `docs/builds/cloth.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- in `in3` (inCHOP)
- in `in4` (inCHOP)
- in `in5` (inCHOP)
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 150x128
- out `out3` (outCHOP)

## Custom parameters

### Sim

| name | label | style | default | value |
|---|---|---|---|---|
| Gridw | Grid width (vertices) | Int | 128 | 150 |
| Gridh | Grid height (vertices) | Int | 128 | 128 |
| Mode | Mode | Menu | cloth | cloth |
| Substeps | Substeps per frame | Int | 16 | 16 |
| Dt | Dt s (0 = 1/cook rate) | Float | 0.0 | 0.0225 |
| Timescale | Time scale | Float | 1.0 | 0.639767 |
| Gravityx | Gravity m/s2 | XYZW | 0.0 | 0.0 |
| Gravityy | Gravity m/s2 | XYZW | -9.8 | -9.8 |
| Gravityz | Gravity m/s2 | XYZW | 0.0 | 0.0 |
| Damping | Damping 1/s | Float | 1.0 | 1.0 |
| Stretch | Stretch compliance | Float | 0.0 | 0.0 |
| Shear | Shear compliance | Float | 0.0001 | 0.0 |
| Bend | Bend compliance | Float | 0.05 | 0.280968 |
| Relax | Jacobi relax | Float | 1.5 | 1.5 |
| Shape | Jelly shape stiffness | Float | 0.1 | 0.1 |
| Mass | Mass kg (whole cloth) | Float | 1.0 | 1.0 |
| Sizew | Width m | Float | 1.0 | 1.0 |
| Sizeh | Height m | Float | 1.0 | 1.0 |
| Orient | Orient | Menu | vertical | vertical |
| Top | Top edge / plane y m | Float | 1.0 | 1.0 |
| Pins | Pins | Menu | top | top |
| Tethers | Tethers to pins | Toggle | True | True |
| Tetherslack | Tether slack | Float | 1.0 | 1.0 |
| Floor | Floor | Toggle | False | False |
| Floory | Floor y m | Float | -0.8 | -0.8 |

### Wind

| name | label | style | default | value |
|---|---|---|---|---|
| Windmode | Windmode | Menu | noise | noise |
| Windx | Wind m/s2 | XYZW | 0.0 | 0.0 |
| Windy | Wind m/s2 | XYZW | 0.0 | 0.0 |
| Windz | Wind m/s2 | XYZW | 3.0 | 3.0 |
| Windgain | Wind gain | Float | 1.0 | 0.939961 |
| Aero | Aero (normal pressure) | Float | 0.7 | 0.7 |
| Turbulence | Turbulence | Float | 0.5 | 0.5 |
| Turbscale | Turbulence scale 1/m | Float | 2.0 | 2.0 |
| Gust | Gust rate Hz | Float | 0.5 | 0.5 |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Bpmdiv | Bpmdiv | Menu | b1 | b1 |
| Burst | Burst | Pulse | False | False |
| Burstforce | Burst m/s2 | Float | 25.0 | 6.98836 |
| Burstdecay | Burst decay s | Float | 0.3 | 0.3 |
| Audiogain | Audio gain | Float | 1.0 | 1.0 |
| Burstthresh | Kick threshold | Float | 0.5 | 0.5 |
| Burstrefractory | Kick gap s | Float | 0.25 | 0.25 |

### Collide

| name | label | style | default | value |
|---|---|---|---|---|
| Friction | Friction | Float | 0.3 | 0.3 |
| Thickness | Thickness m | Float | 0.01 | 0.01 |
| Sphere1on | Sphere 1 | Toggle | False | False |
| Sphere1x | Sphere 1 centre | XYZW | 0.0 | 0.0 |
| Sphere1y | Sphere 1 centre | XYZW | 0.3 | 0.545158 |
| Sphere1z | Sphere 1 centre | XYZW | 0.0 | 0.0 |
| Sphere1r | Sphere 1 radius | Float | 0.3 | 0.3 |
| Sphere2on | Sphere 2 | Toggle | False | False |
| Sphere2x | Sphere 2 centre | XYZW | 0.0 | 0.0 |
| Sphere2y | Sphere 2 centre | XYZW | 0.0 | 0.0 |
| Sphere2z | Sphere 2 centre | XYZW | 0.0 | 0.0 |
| Sphere2r | Sphere 2 radius | Float | 0.2 | 0.2 |
| Sphere3on | Sphere 3 | Toggle | False | False |
| Sphere3x | Sphere 3 centre | XYZW | 0.0 | 0.0 |
| Sphere3y | Sphere 3 centre | XYZW | 0.0 | 0.0 |
| Sphere3z | Sphere 3 centre | XYZW | 0.0 | 0.0 |
| Sphere3r | Sphere 3 radius | Float | 0.2 | 0.2 |
| Sphere4on | Sphere 4 | Toggle | False | False |
| Sphere4x | Sphere 4 centre | XYZW | 0.0 | 0.0 |
| Sphere4y | Sphere 4 centre | XYZW | 0.0 | 0.0 |
| Sphere4z | Sphere 4 centre | XYZW | 0.0 | 0.0 |
| Sphere4r | Sphere 4 radius | Float | 0.2 | 0.2 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Resw | Render width | Int | 1080 | 1080 |
| Resh | Render height | Int | 1920 | 1920 |
| Cam | Cam | Menu | front | front |
| Camdist | Camera distance m | Float | 2.6 | 2.6 |
| Camelev | Camera elevation deg | Float | 10.0 | 10.0 |
| Orbitspeed | Orbit deg/s | Float | 12.0 | 12.0 |
| Fov | Horizontal FOV deg | Float | 40.0 | 40.0 |
| Lightx | Light position | XYZW | 1.5 | 1.5 |
| Lighty | Light position | XYZW | 2.5 | 2.5 |
| Lightz | Light position | XYZW | 3.0 | 3.0 |
| Shading | Shading | Menu | sheen | sheen |
| Colorfrontr | Front colour | RGBA | 0.85 | 0.85 |
| Colorfrontg | Front colour | RGBA | 0.12 | 0.12 |
| Colorfrontb | Front colour | RGBA | 0.25 | 0.25 |
| Colorbackr | Back colour | RGBA | 0.15 | 0.15 |
| Colorbackg | Back colour | RGBA | 0.2 | 0.2 |
| Colorbackb | Back colour | RGBA | 0.55 | 0.55 |
| Texture | Texture | Menu | checker | checker |
| Texmix | Texture mix | Float | 0.5 | 0.5 |
| Texscale | Checker cells | Float | 12.0 | 12.0 |
| Wire | Wire grid | Toggle | False | False |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |
| Alpha | Transparent background | Toggle | False | False |

### Control

| name | label | style | default | value |
|---|---|---|---|---|
| Reset | Reset | Pulse | False | False |
| Pause | Pause | Toggle | False | False |
| Step | Step (paused) | Pulse | False | False |
| Release | Release pins | Pulse | False | False |
| Testmode | Testmode | Menu | off | off |
| Seed | Seed | Int | 1 | 1 |

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
| Zkm1 | Wind | Float | 0.0 | 0.5 |
| Zkm2 | Floppy | Float | 0.0 | 0.5 |
| Zkm3 | Speed | Float | 0.0 | 0.5 |
| Zkm4 | Punch | Float | 0.0 | 0.5 |

### Effectors

| name | label | style | default | value |
|---|---|---|---|---|
| Effon | Effectors on (/project1/effectors) | Toggle | False | False |
| Effselect | Use effectors (all / names / #tags) | StrMenu | all | all |
| Effpad | Collider padding | Float | 0.02 | 0.02 |

## Perf

cook 174.873 ms (CPU 174.873 / GPU 2.303) summed over the 25 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BN_cloth", "parent": "/project1/lab"}` (lands parked)
