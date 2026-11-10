# DC_depth_cam

> depth_cam - `/project1/lab/DC_depth_cam` (live-verified v1 in main, 26 Oct 2026, TD 2025.31550; T-92)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:08 from `/project1/lab/DC_depth_cam`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Depth from the camera: Core ML **Depth Anything V2 Small** (Apple's conversion, Apache-2.0) runs natively in our arm64
vision helper (`helpers/vision_bridge`, request kind 1); the COMP gets a depth TOP and four depth looks behind a
`Mode` par. Client pattern = face_track's: non-blocking, one request in flight, newest frame wins, frame id echoed,
pass-through when the helper or model is missing. Prior art: td-port `lib/depth_fx.py` (port of StageLab's
JZBV_DepthFX logic), whose range/field easing and request controller are copied here.

Build doc: `docs/builds/depth_cam.md`

## Inputs / outputs

- in `in_video` (inTOP) 128x128
- out `out_depth` (outTOP) 2x2
- out `out_info` (outDAT)
- out `out_video` (outTOP) 1920x1080

## Custom parameters

### Depth

| name | label | style | default | value |
|---|---|---|---|---|
| Active | Active (runs the helper) | Toggle | False | False |
| Mode | Mode | Menu | depth | depth |
| Mix | Mix | Float | 1.0 | 1.0 |
| Smooth | Smoothing | Float | 0.5 | 0.5 |
| Hold | Hold s (then pass-through) | Float | 1.0 | 1.0 |
| Invert | Invert depth | Toggle | False | False |
| Mirror | Mirror source | Toggle | False | False |

### Fog

| name | label | style | default | value |
|---|---|---|---|---|
| Fogamount | Fog amount | Float | 1.0 | 1.0 |
| Fogstart | Fog start (far) | Float | 0.3 | 0.3 |
| Fogend | Fog end (far) | Float | 0.9 | 0.9 |
| Fogcolourr | Fog colour | RGBA | 0.06 | 0.06 |
| Fogcolourg | Fog colour | RGBA | 0.08 | 0.08 |
| Fogcolourb | Fog colour | RGBA | 0.14 | 0.14 |

### Slice

| name | label | style | default | value |
|---|---|---|---|---|
| Slicecenter | Slice centre (near) | Float | 0.8 | 0.8 |
| Slicewidth | Slice width | Float | 0.4 | 0.4 |
| Slicesoft | Slice soft edge | Float | 0.05 | 0.05 |
| Slicespeed | Sweep Hz (0 = still) | Float | 0.0 | 0.0 |
| Sliceoutside | Outside level | Float | 0.0 | 0.0 |

### Outline

| name | label | style | default | value |
|---|---|---|---|---|
| Linethresh | Edge threshold | Float | 0.03 | 0.03 |
| Linewidth | Line width px | Float | 2.0 | 2.0 |
| Lineonly | Lines only | Toggle | False | False |
| Linecolourr | Line colour | RGBA | 1.0 | 1.0 |
| Linecolourg | Line colour | RGBA | 1.0 | 1.0 |
| Linecolourb | Line colour | RGBA | 1.0 | 1.0 |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | clip | clip |
| Clipfile | Clip file | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4 |
| Helper | Vision helper binary | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/vision_bridge/build/jzb_vision_bridge | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/vision_bridge/build/jzb_vision_bridge |
| Model | Depth model (.mlmodelc) | Folder | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/vision_bridge/assets/DepthAnythingV2SmallF16.mlmodelc | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/vision_bridge/assets/DepthAnythingV2SmallF16.mlmodelc |
| Fakedepth | Fake depth (test without helper) | Toggle | False | False |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Status | Status | Str | off | off |
| Latency | Round trip median (ms) | Float | 0.0 | 45.0 |
| Rate | Depth maps per s | Float | 0.0 | 0.0 |
| Havedepth | Have depth | Int | 0 | 0 |

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
| Zkm1 | Fog depth | Float | 0.0 | 0.55 |
| Zkm2 | Slice | Float | 0.0 | 0.5 |
| Zkm3 | Lines | Float | 0.0 | 0.5 |

## Perf

cook 0.015 ms (CPU 0.015 / GPU 0.033) summed over the 1 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "DC_depth_cam", "parent": "/project1/lab"}` (lands parked)
