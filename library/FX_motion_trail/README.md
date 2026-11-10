# FX_motion_trail

> motion_trail - `/project1/lab/FX_motion_trail` (TD 2025.31550, 26 Oct 2026)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:23 from `/project1/lab/FX_motion_trail`

Moving things leave a fading trail, coloured by age. Our own clean-room build of the recipe in
`docs/research/BA_motion_tracer.md` section 5 (dcheesman's Patreon .tox was never downloaded or loaded).

Build doc: `docs/builds/motion_trail.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in_level` (inCHOP)
- out `out1` (outTOP) 1920x1080

## Custom parameters

### Trail

| name | label | style | default | value |
|---|---|---|---|---|
| Length | Length | Int | 30 | 30 |
| Lengthunit | Unit | Menu | frames | frames |
| Beats | Beats | Float | 1.0 | 1.0 |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Decay | Decay | Float | 0.5 | 0.5 |
| Threshold | Threshold | Float | 0.08 | 0.08 |
| Softness | Softness | Float | 0.05 | 0.05 |
| Mix | Mix | Float | 1.0 | 1.0 |
| Sourcelevel | Source lvl | Float | 1.0 | 1.0 |
| Audioamount | Audio mix | Float | 0.0 | 0.0 |
| Hold | Hold | Toggle | False | False |
| Clear | Clear | Pulse | False | False |

### Colour

| name | label | style | default | value |
|---|---|---|---|---|
| Agecolor | Age colour | Menu | ramp | palette |
| Blend | Blend | Menu | over | over |
| Colornewr | New | RGBA | 1.0 | 1.0 |
| Colornewg | New | RGBA | 1.0 | 1.0 |
| Colornewb | New | RGBA | 1.0 | 1.0 |
| Colormidr | Mid | RGBA | 0.62 | 0.62 |
| Colormidg | Mid | RGBA | 0.64 | 0.64 |
| Colormidb | Mid | RGBA | 0.68 | 0.68 |
| Coloroldr | Old | RGBA | 0.22 | 0.22 |
| Coloroldg | Old | RGBA | 0.23 | 0.23 |
| Coloroldb | Old | RGBA | 0.26 | 0.26 |
| Palette | Palette | Menu | custom | custom |
| Palettesmooth | Smooth pal | Toggle | True | True |
| Spread | Spread | Float | 1.0 | 1.0 |
| Cycle | Cycle /s | Float | 0.0 | 0.0 |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | clip | clip |
| Clipfile | Clip file | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 |
| Quality | Working size | Menu | half | half |
| Resetonloop | Clear at clip loop point | Toggle | True | True |
| Palettefile | Palette file (.txt .hex .json .gpl .pal .ase) | File |  | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/palettes/trail_test.gpl |

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
| Zkm1 | Trail | Float | 0.0 | 0.3 |
| Zkm2 | Sensitivity | Float | 0.0 | 0.6 |
| Zkm3 | Colour | Float | 0.0 | 0.25 |
| Zkm4 | Fade | Float | 0.0 | 1.0 |

## Perf

cook 0.804 ms (CPU 0.804 / GPU 0.702) summed over the 10 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_motion_trail", "parent": "/project1/lab"}` (lands parked)
