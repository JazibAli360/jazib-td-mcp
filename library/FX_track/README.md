# FX_track

> fx_track: FX_track rack + shared tracker + plexus / hud / analytics (lane F, 27 Oct 2026, TD 2025.31550 target)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:08:36 from `/project1/lab/FX_track`

`/project1/lab/FX_track`. Plan: `docs/builds/BUILD_PLAN_27OCT.md` s2 ("FX_track YES, small": one tracker shared by
plexus, HUD and analytics) and lane F. Specs: FX7b **TC-01** (blob plexus), **TC-02** (tracking HUD), **TC-04**
(surveillance analytics). Technique emulation from the public descriptions (elekktronaut T76, Dean Cheesman blob
tracker 2026, Gaku Lange / Guinutil tracking-VFX trend, uisato A.S.S.); no files of theirs used.

**Status: verified live on build TD b2 (2025.31550)**: tracker + plexus + hud + analytics, see "Verified live".
14 offline tests incl. glslc of every pass.

Build doc: `docs/builds/fx_track.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Track

| name | label | style | default | value |
|---|---|---|---|---|
| Tracksrc | Tracksrc | Menu | picture | picture |
| Tracktop | Track TOP (e.g. CV_person_mask/out2) | TOP |  |  |
| Key | Key | Menu | bright | bright |
| Keygain | Key gain | Float | 1.0 | 1.0 |
| Motiongain | Motion gain | Float | 6.0 | 6.0 |
| Threshold | Threshold (key) | Float | 0.55 | 0.55 |
| Detector | Detector | Menu | cells | cells |
| Cellsx | Cells across | Int | 18 | 18 |
| Cellsy | Cells down | Int | 32 | 32 |
| Cellpick | Cellpick | Menu | peak | peak |
| Minfill | Min share of a cell over threshold | Float | 0.03 | 0.03 |
| Smooth | Smooth (kept share per frame) | Float | 0.5 | 0.5 |
| Maxblobs | Max blobs | Int | 32 | 32 |
| Blobmin | Blob min size | Float | 0.02 | 0.02 |
| Blobmax | Blob max size | Float | 0.3 | 0.3 |
| Blobmove | Blob max move | Float | 0.05 | 0.05 |
| Detw | Detect width px | Int | 270 | 270 |
| Deth | Detect height px | Int | 480 | 480 |
| Resw | Picture width (plexus lines) | Int | 1080 | 1080 |
| Resh | Picture height (plexus lines) | Int | 1920 | 1920 |
| Outpts | Points out (out_pts CHOP, strongest kept) | Int | 64 | 64 |

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (passthrough) | Toggle | False | False |
| Input | Input | Menu | auto | auto |

## Perf

cook 8.454 ms (CPU 8.454 / GPU 0.143) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_track", "parent": "/project1/lab"}` (lands parked)
