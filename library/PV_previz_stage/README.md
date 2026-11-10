# PV_previz_stage

> previz_stage (`/project1/lab/PV_previz_stage`)

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:39 from `/project1/lab/PV_previz_stage`

Drop any TOP into a stage previz: LED wall in a hazy hall, a seeded instanced crowd, beams and wash light that take
the screen's colour, camera presets. Clean-room design from `docs/research/BI_rudiment_previz_stage.md`, with a
generic wall (no show-specific layout). TD 2025.31550.

Build doc: `docs/builds/previz_stage.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in_audio` (inCHOP)
- out `out1` (outTOP) 1920x1080
- out `out_react` (outCHOP)

## Custom parameters

### Stage

| name | label | style | default | value |
|---|---|---|---|---|
| Layout | Wall layout | Menu | flat | sides |
| Wallw | Main width (m) | Float | 12.0 | 14.1 |
| Wallh | Main height (m) | Float | 6.75 | 6.75 |
| Curve | Main curve (deg) | Float | 0.0 | 0.0 |
| Sidew | Side width (m) | Float | 4.0 | 4.0 |
| Sideh | Side height (m) | Float | 6.0 | 6.0 |
| Sidefold | Side fold (deg) | Float | 20.0 | 20.0 |
| Gap | Gap between faces (m) | Float | 1.5 | 1.5 |
| Contentmap | Content on faces | Menu | span | span |
| Screenelev | Screen above deck (m) | Float | 1.0 | 1.0 |
| Screenemit | Screen brightness | Float | 1.0 | 1.0 |
| Stageh | Deck height (m) | Float | 1.2 | 1.2 |
| Stagedepth | Deck depth (m) | Float | 10.0 | 10.0 |
| Trussh | Truss height (m) | Float | 10.5 | 10.5 |
| Trussz | Truss distance from wall (m) | Float | 3.0 | 3.0 |

### Crowd

| name | label | style | default | value |
|---|---|---|---|---|
| Crowdon | Crowd on | Toggle | True | True |
| Count | Count | Int | 800 | 800 |
| Rows | Rows | Int | 20 | 20 |
| Spacing | Spacing (m) | Float | 0.65 | 0.65 |
| Crowdgap | Gap to stage (m) | Float | 3.0 | 3.0 |
| Heightvar | Height variation | Float | 0.08 | 0.08 |
| Seed | Seed | Int | 1 | 1 |
| Sway | Sway | Float | 0.3 | 0.3 |
| Swayspeed | Sway speed | Float | 0.5 | 0.5 |
| Hands | Raised hands (fraction) | Float | 0.15 | 0.15 |
| Crowdlit | Screen light on crowd | Float | 1.0 | 1.0 |

### Haze

| name | label | style | default | value |
|---|---|---|---|---|
| Hazeon | Haze on | Toggle | True | True |
| Density | Density | Float | 0.5 | 0.5 |
| Falloff | Height falloff | Float | 1.0 | 1.0 |
| Drift | Drift speed | Float | 0.05 | 0.05 |
| Scatter | Beam visibility | Float | 0.6 | 0.6 |
| Hazeglow | Screen glow in haze | Float | 0.5 | 0.5 |

### Lights

| name | label | style | default | value |
|---|---|---|---|---|
| Lightson | Lights on | Toggle | True | True |
| Beams | Beams | Int | 8 | 8 |
| Spread | Beam spread (deg) | Float | 6.0 | 6.0 |
| Fan | Fan (deg) | Float | 50.0 | 50.0 |
| Beamtilt | Tilt to crowd (deg) | Float | 30.0 | 30.0 |
| Beamlen | Beam length (m) | Float | 30.0 | 30.0 |
| Intensity | Intensity | Float | 1.0 | 1.0 |
| Follow | Follow screen colour | Float | 1.0 | 1.0 |
| Reactmode | React mode | Menu | average | average |
| Reactlag | React lag (s) | Float | 0.2 | 0.2 |
| Beamsweep | Sweep | Float | 0.3 | 0.3 |
| Beamsweepspeed | Sweep speed (Hz) | Float | 0.2 | 0.2 |
| Wash | Wash light | Float | 1.0 | 1.0 |
| Strobe | Strobe | Float | 0.0 | 0.0 |
| Strobehz | Strobe rate (Hz) | Float | 4.0 | 4.0 |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Preset | Camera preset | Menu | foh | foh |
| Fov | Field of view (deg) | Float | 45.0 | 36.2 |
| Orbitx | Orbit yaw (deg) | Float | 0.0 | 0.0 |
| Orbity | Orbit pitch (deg) | Float | 0.0 | 0.0 |
| Orbitdist | Distance x | Float | 1.0 | 1.0 |
| Autoorbit | Auto orbit | Toggle | False | False |
| Orbitspeed | Orbit speed (deg/s) | Float | 5.0 | 5.0 |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Screen source | Menu | input | noise |
| Resx | Width | Int | 1920 | 1920 |
| Resy | Height | Int | 1080 | 1080 |
| Msaa | Antialias | Menu | aa4 | aa4 |
| Showscreenonly | Show screen only | Toggle | False | False |
| Exposure | Exposure (stops) | Float | 0.0 | 0.0 |
| Bloom | Bloom | Float | 0.5 | 0.5 |
| Texw | Screen texture width | Int | 1920 | 1920 |
| Quality | Quality | Menu | high | high |
| Bloomres | Bloom resolution | Menu | quarter | quarter |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audioreact | Audio to beams | Float | 0.0 | 0.0 |
| Audiogain | Audio gain | Float | 1.0 | 1.0 |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Basecolorr | Beam base colour | RGBA | 1.0 | 1.0 |
| Basecolorg | Beam base colour | RGBA | 1.0 | 1.0 |
| Basecolorb | Beam base colour | RGBA | 1.0 | 1.0 |
| Hazecolorr | Haze colour | RGBA | 0.55 | 0.55 |
| Hazecolorg | Haze colour | RGBA | 0.6 | 0.6 |
| Hazecolorb | Haze colour | RGBA | 0.7 | 0.7 |
| Testcolorr | Test colour | RGBA | 1.0 | 0.0 |
| Testcolorg | Test colour | RGBA | 0.0 | 1.0 |
| Testcolorb | Test colour | RGBA | 0.0 | 0.0 |

### Window

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls window | Pulse | False | False |
| Openview | Open view window | Pulse | False | False |
| Reset | Reset to defaults | Pulse | False | False |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 46 |
| Zkcols | Columns | Int | 8 | 12 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Haze | Float | 0.0 | 0.33 |
| Zkm2 | Light | Float | 0.0 | 0.42 |
| Zkm3 | Motion | Float | 0.0 | 0.25 |
| Zkm4 | Crowd | Float | 0.0 | 0.25 |

## Perf

cook 312.509 ms (CPU 312.509 / GPU 4.159) summed over the 24 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "PV_previz_stage", "parent": "/project1/lab"}` (lands parked)
