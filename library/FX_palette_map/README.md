# FX_palette_map

> palette_map - `/project1/lab/FX_palette_map` (TD 2025.31550, 26 Oct 2026)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:24 from `/project1/lab/FX_palette_map`

Maps every pixel to the nearest colour of a palette (OKLab or sRGB distance), with ordered / noise dither, blend
and preserve-luma. Our own clean-room build of the recipe in `docs/research/AZ_closest_color_palette.md` section 4
(idea credit: "Closest Color Palette TOX" by percolated, derivative.ca asset 69695; never downloaded or loaded).

Build doc: `docs/builds/palette_map.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- out `out1` (outTOP) 128x128

## Custom parameters

### Palette

| name | label | style | default | value |
|---|---|---|---|---|
| Palette | Palette | Menu | pico8 | pico8 |
| Colourspace | Colour space | Menu | oklab | oklab |
| Blend | Blend | Float | 1.0 | 1.0 |
| Lightnessweight | Lightness weight | Float | 1.0 | 1.0 |
| Preserveluma | Preserve luma | Float | 0.0 | 0.0 |
| Dither | Dither | Menu | off | off |
| Ditheramount | Dither amount | Float | 1.0 | 1.0 |
| Ditheranimate | Animate dither | Toggle | False | False |
| Copytotable | Copy to table | Pulse | False | False |
| Load | Load file | Pulse | False | False |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| File | Palette file (.txt .hex .json .gpl .pal .ase) | File |  |  |
| Count | Colours (read-only) | Int | 0 | 16 |
| Source | Source | Menu | auto | auto |
| Clipfile | Clip file | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 |

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
| Zkm1 | Strength | Float | 0.0 | 1.0 |
| Zkm2 | Grit | Float | 0.0 | 0.5 |

## Perf

cook 0.016 ms (CPU 0.016 / GPU 0.025) summed over the 1 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_palette_map", "parent": "/project1/lab"}` (lands parked)
