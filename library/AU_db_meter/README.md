# AU_db_meter

> db_meter (`/project1/lab/AU_db_meter`)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:36 from `/project1/lab/AU_db_meter`

Stereo peak / RMS level meter: dB scale, peak hold line, clip lamps, labels that line up with the bars at any size,
vertical or horizontal. Clean-room design from `docs/research/BG_rudiment_db_meter.md`. Built and checked on TD 2025.31550.

Build doc: `docs/builds/db_meter.md`

## Inputs / outputs

- in `in1` (inCHOP)
- out `out1` (outTOP) 256x1024
- out `out2` (outCHOP)

## Custom parameters

### Meter

| name | label | style | default | value |
|---|---|---|---|---|
| Mode | Mode | Menu | peak | peak |
| Floor | Floor dB | Float | -60.0 | -60.0 |
| Ceil | Ceil dB | Float | 3.0 | 3.0 |
| Step | Label step dB | Float | 6.0 | 6.0 |
| Gain | Gain dB | Float | 0.0 | 0.0 |
| Attack | Attack s | Float | 0.0 | 0.0 |
| Release | Release dB/s | Float | 24.0 | 24.0 |
| Hold | Peak/clip hold s | Float | 1.5 | 1.5 |
| Clipdb | Clip at dB | Float | 0.0 | 0.0 |
| Holdreset | Reset hold | Pulse | False | False |

### Input

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | input | input |
| Channels | Channels | Menu | auto | auto |
| Testamp | Test amplitude | Float | 0.5 | 0.5 |
| Testfreq | Test Hz | Float | 440.0 | 440.0 |
| Testchan | Testchan | Menu | both | both |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Resw | Width | Int | 256 | 256 |
| Resh | Height | Int | 1024 | 1024 |
| Orient | Orient | Menu | vertical | vertical |
| Gap | Bar gap px | Float | 4.0 | 4.0 |
| Scalew | Scale strip | Float | 0.4 | 0.4 |
| Showscale | Scale | Toggle | True | True |
| Showpeak | Peak hold line | Toggle | True | True |
| Peakpx | Peak line px | Float | 2.0 | 2.0 |
| Fontsize | Font px (0 auto) | Float | 0.0 | 0.0 |
| Transparent | Transparent bg | Toggle | False | False |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Gradlowr | Low | RGBA | 0.1 | 0.1 |
| Gradlowg | Low | RGBA | 0.62 | 0.62 |
| Gradlowb | Low | RGBA | 0.22 | 0.22 |
| Gradmidr | Mid (-6 dB) | RGBA | 0.9 | 0.9 |
| Gradmidg | Mid (-6 dB) | RGBA | 0.78 | 0.78 |
| Gradmidb | Mid (-6 dB) | RGBA | 0.12 | 0.12 |
| Gradhighr | High (0 dB) / clip | RGBA | 0.95 | 0.95 |
| Gradhighg | High (0 dB) / clip | RGBA | 0.18 | 0.18 |
| Gradhighb | High (0 dB) / clip | RGBA | 0.12 | 0.12 |
| Trackr | Track | RGBA | 0.16 | 0.16 |
| Trackg | Track | RGBA | 0.16 | 0.16 |
| Trackb | Track | RGBA | 0.17 | 0.17 |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |
| Peakcolr | Peak line | RGBA | 0.92 | 0.92 |
| Peakcolg | Peak line | RGBA | 0.92 | 0.92 |
| Peakcolb | Peak line | RGBA | 0.92 | 0.92 |
| Labelcolr | Labels | RGBA | 0.8 | 0.8 |
| Labelcolg | Labels | RGBA | 0.8 | 0.8 |
| Labelcolb | Labels | RGBA | 0.8 | 0.8 |

### Controls

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Smooth | Float | 0.0 | 0.65 |
| Zkm2 | Range | Float | 0.0 | 0.5 |

## Perf

cook 33.698 ms (CPU 33.698 / GPU 0.103) summed over the 5 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "AU_db_meter", "parent": "/project1/lab"}` (lands parked)
