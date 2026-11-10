# FX_strobe

> strobe: FX_strobe strobe effector (26 Oct 2026, TD 2025.31550)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:30 from `/project1/lab/FX_strobe`

`/project1/lab/FX_strobe`. A self-contained TOP strobe: picture in, flashed picture out. Spec/recipe:
`docs/research/AX_strobber.md` (our own clean-room design; idea credit: Strobber by Skywalker.Visuals, no licence
stated; nothing of its files used). **No limits** (user rule): open ranges, no flash cap, no limiter; Hold = 0 means
every trigger flashes. The operator decides.

In: `in1` TOP (picture), `in2` CHOP (`low` `level` `kick` 0..1, e.g. `AC_audio/ctl_out`). Out: `out1` TOP only.
Test inputs inside: `test_noise` (1080x1920 noise) and `test_kick` (square 0..1 at Testrate Hz) + `test_wave`
(sine low/level at Testrate/4). `Input` menu: auto (in1/in2 when wired, else test) / live / test.

Build doc: `docs/builds/strobe.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inCHOP)
- out `out1` (outTOP) 128x128

## Custom parameters

### Trigger

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | kick | kick |
| Threshold | Threshold | Float | 0.6 | 0.6 |
| Division | Every Nth | Menu | 1 | 1 |
| Hold | Hold gap s | Float | 0.0 | 0.0 |
| Rate | LFO rate Hz | Float | 2.0 | 2.0 |

### Tempo

| name | label | style | default | value |
|---|---|---|---|---|
| Tempo | Tempo | Menu | project | project |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Tap | Tap | Pulse | False | False |
| Note | Note | Menu | n4 | n4 |
| Notemod | Feel | Menu | straight | straight |
| Phase | Phase | Float | 0.0 | 0.0 |
| Swing | Swing | Float | 0.0 | 0.0 |
| Resync | Resync | Pulse | False | False |

### Manual

| name | label | style | default | value |
|---|---|---|---|---|
| Fire | Fire | Pulse | False | False |
| Flash | Flash (hold) | Momentary | False | False |
| Burst | Burst | Pulse | False | False |
| Burstcount | Burst hits | Int | 4 | 4 |
| Key | Fire key | Str | space | space |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Mode | Mode | Menu | lift | lift |
| Attack | Attack s | Float | 0.01 | 0.01 |
| Release | Release s | Float | 0.15 | 0.15 |
| Ease | Ease | Menu | linear | linear |
| Depth | Depth | Float | 1.0 | 1.0 |
| Mix | Mix | Float | 1.0 | 1.0 |
| Colourr | Colour | RGBA | 1.0 | 1.0 |
| Colourg | Colour | RGBA | 1.0 | 1.0 |
| Colourb | Colour | RGBA | 1.0 | 1.0 |
| Blackout | Blackout | Toggle | False | False |

### Input

| name | label | style | default | value |
|---|---|---|---|---|
| Input | Input source | Menu | auto | auto |
| Testrate | Test pulse Hz | Float | 2.0 | 2.0 |
| Linkchop | Link CHOP (tempo) | CHOP |  |  |

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
| Zkm1 | Intensity | Float | 0.0 | 1.0 |
| Zkm2 | Snap | Float | 0.0 | 0.85 |
| Zkm3 | Speed | Float | 0.0 | 0.3 |

## Perf

cook 0.226 ms (CPU 0.226 / GPU 0.11) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_strobe", "parent": "/project1/lab"}` (lands parked)
