# CV_person_mask

> person_mask - `/project1/lab/CV_person_mask` (TD 2025.31550, 26 Oct 2026)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:07 from `/project1/lab/CV_person_mask`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Apple Vision person matte -> premultiplied cut-out, matte and inverse. Uses the AppleVisionMask C++ TOP
(`helpers/bgremoval/build/AppleVisionMask.plugin`, provenance `helpers/bgremoval/README.md`) loaded **by absolute
path** at runtime, never from the per-user Plugins folder (T-81, T-99).

**State:** built on the main TD with **Visionon off** (plugin not loaded there: the main-TD load waits for the user's
OK, `docs/builds/bg_person_mask.md`). With Vision off the matte is full (pass-through). Everything below with Vision
on was verified on the **scratch TD**. To turn it on in the main TD: `Setup > Vision on` (or
`build('/project1/lab', vision=True)`); load before doors (native load).

Build doc: `docs/builds/person_mask.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- out `out1` (outTOP) 1920x1080
- out `out2` (outTOP) 1920x1080
- out `out3` (outTOP) 1920x1080

## Custom parameters

### Matte

| name | label | style | default | value |
|---|---|---|---|---|
| Feather | Feather px | Float | 2.0 | 2.0 |
| Grow | Choke/grow px | Float | 0.0 | 0.0 |
| Smooth | Temporal smooth | Float | 0.3 | 0.3 |
| Invert | Invert | Toggle | False | False |
| Opacity | Opacity | Float | 1.0 | 1.0 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Person | Person | Menu | source | source |
| Fillcolorr | Fill colour | RGBA | 1.0 | 1.0 |
| Fillcolorg | Fill colour | RGBA | 1.0 | 1.0 |
| Fillcolorb | Fill colour | RGBA | 1.0 | 1.0 |
| Background | Background | Menu | none | none |
| Bgcolorr | Bg colour | RGBA | 0.0 | 0.0 |
| Bgcolorg | Bg colour | RGBA | 0.0 | 0.0 |
| Bgcolorb | Bg colour | RGBA | 0.0 | 0.0 |
| Bgalpha | Bg alpha | Float | 1.0 | 1.0 |
| View | View on out1 | Menu | cutout | cutout |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| Visionon | Vision on (loads the C++ plugin) | Toggle | False | True |
| Quality | Vision quality | Menu | Balanced | Balanced |
| Inputscale | Vision input size | Menu | half | half |
| Visionres | Vision resolution | Menu | Input | Input |
| Rgbdelay | RGB delay | Menu | match | match |
| Source | Source | Menu | clip | clip |
| Clipfile | Clip file | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 |
| Pluginpath | Plugin path | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/bgremoval/build/AppleVisionMask.plugin | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/bgremoval/build/AppleVisionMask.plugin |
| Resetsmooth | Reset smoothing | Pulse | False | False |

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
| Zkm1 | Edge | Float | 0.0 | 0.33 |
| Zkm2 | Wrap | Float | 0.0 | 0.0 |

### Wrap

| name | label | style | default | value |
|---|---|---|---|---|
| Lightwrap | Light wrap | Float | 0.0 | 0.0 |
| Wrapwidth | Wrap width px | Float | 12.0 | 12.0 |
| Wrapblur | Wrap light blur px | Float | 24.0 | 24.0 |
| Wrapgamma | Wrap falloff (gamma) | Float | 1.0 | 1.0 |
| Wrapsrc | Wrap light from | Menu | background | background |
| Despill | Despill (green -> max(r, b)) | Float | 0.0 | 0.0 |

## Perf

cook 3.648 ms (CPU 3.648 / GPU 14.108) summed over the 15 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "CV_person_mask", "parent": "/project1/lab"}` (lands parked)
