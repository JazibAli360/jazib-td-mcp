# FT_face_track

> face_track - `/project1/lab/FT_face_track` (TD 2025.31550, 26 Oct 2026)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:09 from `/project1/lab/FT_face_track`

Clean-room take on vankrav's "Face Tracking" rudiment (spec: `docs/research/BH_rudiment_face_tracking.md`).
Apple Vision face landmarks from a native arm64 helper (`helpers/vision_bridge`, kind 5) -> CHOPs, masks, wire overlay.

Build doc: `docs/builds/face_track.md`

## Inputs / outputs

- in `in_video` (inTOP) 128x128
- out `out_ctl` (outCHOP)
- out `out_eyes` (outTOP) 512x144
- out `out_face` (outTOP) 512x144
- out `out_info` (outDAT)
- out `out_mouth` (outTOP) 512x144
- out `out_pts` (outCHOP)
- out `out_video` (outTOP) 1920x540

## Custom parameters

### Track

| name | label | style | default | value |
|---|---|---|---|---|
| Active | Active (runs the helper) | Toggle | False | False |
| Maxfaces | Max faces | Int | 4 | 4 |
| Smooth | Smoothing (One-Euro) | Float | 0.5 | 0.5 |
| Minconf | Min confidence | Float | 0.5 | 0.5 |
| Holdframes | Hold frames on loss | Int | 8 | 8 |
| Mirror | Mirror source | Toggle | False | False |
| Showwire | Show wire | Toggle | True | True |
| Showboxes | Show face boxes | Toggle | False | False |
| Wirewidth | Wire width (px) | Float | 2.0 | 2.0 |
| Wireopacity | Wire opacity | Float | 1.0 | 1.0 |
| Maskblur | Mask blur (px) | Float | 4.0 | 4.0 |
| Maskgrow | Mask grow (x0.1% h) | Float | 0.0 | 0.0 |
| Eyeexpand | Eye mask scale | Float | 1.3 | 1.3 |
| Mouthexpand | Mouth mask scale | Float | 1.1 | 1.1 |
| Forehead | Face mask forehead | Float | 0.25 | 0.25 |
| Opencontrols | Open controls window | Pulse | False | False |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | clip | clip |
| Clipfile | Clip file | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/faces/ward_cunningham_8s_twofaces.mp4 |
| Detectsize | Detect width | Menu | w640 | w640 |
| Maskres | Mask resolution | Menu | r512 | r512 |
| Rollunit | Roll / yaw / pitch unit | Menu | deg | deg |
| Helper | Vision helper binary | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/vision_bridge/build/jzb_vision_bridge | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/vision_bridge/build/jzb_vision_bridge |
| Eyeclosed | Eye ratio closed | Float | 0.12 | 0.12 |
| Eyeopen | Eye ratio open | Float | 0.35 | 0.35 |
| Mouthrest | Mouth ratio at rest | Float | 0.02 | 0.02 |
| Mouthmax | Mouth ratio wide open | Float | 0.6 | 0.6 |
| Calibrate | Calibrate rest pose (face 1) | Pulse | False | False |
| Fakeface | Fake face (test without helper) | Toggle | False | False |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Wirecolorr | Wire colour | RGBA | 1.0 | 1.0 |
| Wirecolorg | Wire colour | RGBA | 1.0 | 1.0 |
| Wirecolorb | Wire colour | RGBA | 1.0 | 1.0 |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Facecount | Faces tracked | Int | 0 | 0 |
| Latency | Round trip median (ms) | Float | 0.0 | 0.0 |
| Status | Status | Str | off | off |

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
| Zkm1 | Steady | Float | 0.0 | 0.5 |
| Zkm2 | Mask soft | Float | 0.0 | 0.5 |
| Zkm3 | Features | Float | 0.0 | 0.5 |

## Perf

cook 31.754 ms (CPU 31.754 / GPU 10.136) summed over the 4 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FT_face_track", "parent": "/project1/lab"}` (lands parked)
