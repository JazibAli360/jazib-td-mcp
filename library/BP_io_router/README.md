# BP_io_router

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:05 from `/project1/lab/BP_io_router`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- in `in3` (inTOP) 128x128
- in `in4` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 1080x1920
- out `out3` (outTOP) 1080x1920
- out `out4` (outTOP) 1080x1920
- out `out5` (outTOP) 1080x1920
- out `out6` (outCHOP)
- out `out7` (outDAT)

## Custom parameters

### Bus

| name | label | style | default | value |
|---|---|---|---|---|
| Busa | Bus A | Menu | s1 | s1 |
| Busb | Bus B | Menu | s2 | s2 |
| Mix | Mix A-B | Float | 0.0 | 0.0 |
| Xfademode | Fade mode | Menu | manual | manual |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Cutdiv | Cut on beats | Menu | 1 | 1 |
| Xfadetime | Fade time s | Float | 0.0 | 0.0 |
| Fadecurve | Fade curve | Menu | linear | linear |
| Cutnow | Cut now | Pulse | False | False |
| Stalesec | Stale after s | Float | 1.0 | 1.0 |
| Refreshsources | Refresh status | Pulse | False | False |

### Sources

| name | label | style | default | value |
|---|---|---|---|---|
| S1kind | S1 kind | Menu | test | local |
| S1name | S1 NDI/Syphon name | Str |  |  |
| S1active | S1 NDI receive on | Toggle | False | False |
| S1inalpha | S1 alpha in | Menu | premult | premult |
| S1res | S1 res | Menu | 1080x1920 | 1080x1920 |
| S1resw | S1 custom w | Int | 1080 | 1080 |
| S1resh | S1 custom h | Int | 1920 | 1920 |
| S1fit | S1 fit | Menu | fitbest | fitbest |
| S1file | S1 movie file | File |  |  |
| S2kind | S2 kind | Menu | off | test |
| S2name | S2 NDI/Syphon name | Str |  |  |
| S2active | S2 NDI receive on | Toggle | False | False |
| S2inalpha | S2 alpha in | Menu | premult | straight |
| S2res | S2 res | Menu | 1080x1920 | 1080x1920 |
| S2resw | S2 custom w | Int | 1080 | 1080 |
| S2resh | S2 custom h | Int | 1920 | 1920 |
| S2fit | S2 fit | Menu | fitbest | fitbest |
| S2file | S2 movie file | File |  |  |
| S3kind | S3 kind | Menu | off | off |
| S3name | S3 NDI/Syphon name | Str |  |  |
| S3active | S3 NDI receive on | Toggle | False | False |
| S3inalpha | S3 alpha in | Menu | premult | premult |
| S3res | S3 res | Menu | 1080x1920 | 1080x1920 |
| S3resw | S3 custom w | Int | 1080 | 1080 |
| S3resh | S3 custom h | Int | 1920 | 1920 |
| S3fit | S3 fit | Menu | fitbest | fitbest |
| S3file | S3 movie file | File |  |  |
| S4kind | S4 kind | Menu | off | off |
| S4name | S4 NDI/Syphon name | Str |  |  |
| S4active | S4 NDI receive on | Toggle | False | False |
| S4inalpha | S4 alpha in | Menu | premult | premult |
| S4res | S4 res | Menu | 1080x1920 | 1080x1920 |
| S4resw | S4 custom w | Int | 1080 | 1080 |
| S4resh | S4 custom h | Int | 1920 | 1920 |
| S4fit | S4 fit | Menu | fitbest | fitbest |
| S4file | S4 movie file | File |  |  |

### Sinks

| name | label | style | default | value |
|---|---|---|---|---|
| O1kind | O1 kind | Menu | off | syphon |
| O1src | O1 source | Menu | bus | s1 |
| O1name | O1 sender name | Str | TD_BP_io_router_1 | jazib-td master |
| O1active | O1 SEND (go-ahead) | Toggle | False | False |
| O1outalpha | O1 alpha out | Menu | premult | straight |
| O1fmt | O1 format | Menu | fixed8 | fixed8 |
| O1skip | O1 NDI skip frames | Toggle | True | True |
| O1res | O1 res | Menu | input | input |
| O1resw | O1 custom w | Int | 1080 | 1080 |
| O1resh | O1 custom h | Int | 1920 | 1920 |
| O2kind | O2 kind | Menu | off | ndi |
| O2src | O2 source | Menu | bus | bus |
| O2name | O2 sender name | Str | TD_BP_io_router_2 | TD_BP_io_router_2 |
| O2active | O2 SEND (go-ahead) | Toggle | False | False |
| O2outalpha | O2 alpha out | Menu | premult | none |
| O2fmt | O2 format | Menu | fixed8 | fixed8 |
| O2skip | O2 NDI skip frames | Toggle | True | True |
| O2res | O2 res | Menu | input | input |
| O2resw | O2 custom w | Int | 1080 | 1080 |
| O2resh | O2 custom h | Int | 1920 | 1920 |
| O3kind | O3 kind | Menu | off | off |
| O3src | O3 source | Menu | bus | bus |
| O3name | O3 sender name | Str | TD_BP_io_router_3 | TD_BP_io_router_3 |
| O3active | O3 SEND (go-ahead) | Toggle | False | False |
| O3outalpha | O3 alpha out | Menu | premult | premult |
| O3fmt | O3 format | Menu | fixed8 | fixed8 |
| O3skip | O3 NDI skip frames | Toggle | True | True |
| O3res | O3 res | Menu | input | input |
| O3resw | O3 custom w | Int | 1080 | 1080 |
| O3resh | O3 custom h | Int | 1920 | 1920 |
| O4kind | O4 kind | Menu | off | off |
| O4src | O4 source | Menu | bus | bus |
| O4name | O4 sender name | Str | TD_BP_io_router_4 | TD_BP_io_router_4 |
| O4active | O4 SEND (go-ahead) | Toggle | False | False |
| O4outalpha | O4 alpha out | Menu | premult | premult |
| O4fmt | O4 format | Menu | fixed8 | fixed8 |
| O4skip | O4 NDI skip frames | Toggle | True | True |
| O4res | O4 res | Menu | input | input |
| O4resw | O4 custom w | Int | 1080 | 1080 |
| O4resh | O4 custom h | Int | 1920 | 1920 |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 48 |
| Zkcols | Columns | Int | 8 | 10 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |

## Perf

cook 93.959 ms (CPU 93.959 / GPU 1.161) summed over the 29 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BP_io_router", "parent": "/project1/lab"}` (lands parked)
