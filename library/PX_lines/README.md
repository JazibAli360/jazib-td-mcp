# PX_lines

> PX_lines: the lines pass for point / splat scenes (lane W1-C, 27 Oct 2026, TD 2025.31550 target)

v0.2.0 - TD 2025.31550 - exported 2026-10-29 00:09:22 from `/project1/lab/PX_lines`

User (27 Oct): "including the green lines ... and all", colours changeable. Ruben Fro's thin bright neon lines
(`RUBENFRO_COVERAGE.md` 1a, G1-G7; evidence `docs/research/BR_rubenfro_pointcloud_fx.md` 4d.1, frames in
`research_src/rubenfro/yt2/`). **Status: phase 1 OFFLINE done** (builder + numpy references + 35 offline tests +
glslc). **Phase 2 LIVE done on the scratch TD (27 Oct, 2025.31550): LC1-LC14 pass; results in "Verified live" at the
end; then built in main by the builder (see "In main").**

One COMP, `PX_lines`, usable two ways:
* **standalone over any TOP**: `in1` = scene, `in_points` = any rgba32f TOP whose texels are xyz, `in_depth` = linear
  eye depth (optional), own `cam` or `Camera` = any Camera COMP; `out1` = lines composited over `in1`.
* **as PX's lines layer** (wave-2 PX owner wires it; this lane did not edit `px.py` / `px_logic.py`): build it inside
  `PX_pointfx` (`build('/project1/lab/PX_pointfx')`), `Outmode` lines, `in_points` = PX `update` (state texture),

Build doc: `docs/builds/px_lines.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in_depth` (inTOP) 128x128
- in `in_points` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Lines

| name | label | style | default | value |
|---|---|---|---|---|
| Amount | Amount | Float | 1.0 | 1.0 |
| Outmode | Outmode | Menu | composite | composite |
| Maxseg | Segment budget | Int | 65536 | 43311 |
| Width | Core width px | Float | 2.0 | 7.68 |
| Halo | Halo radius px | Float | 6.0 | 6.0 |
| Halogain | Halo gain | Float | 0.35 | 0.35 |
| Intensity | Intensity (HDR) | Float | 1.5 | 1.5 |
| Blend | Blend | Menu | max | max |
| Bgdim | Dim the scene under the lines | Float | 0.0 | 0.0 |
| Resx | Output width | Int | 1080 | 1080 |
| Resy | Output height | Int | 1920 | 1920 |
| Camera | Camera (empty = own cam) | COMP |  |  |
| Speed | Time speed | Float | 1.0 | 1.0 |
| Seed | Seed | Int | 1 | 1 |
| Reset | Reset trails | Pulse | False | False |
| Resetn | Reset count (internal) | Int | 0 | 0 |

### Reveal

| name | label | style | default | value |
|---|---|---|---|---|
| Reveal | Reveal (draw-on 0..1) | Float | 1.0 | 1.0 |
| Cut | Cut (erase from start) | Float | 0.0 | 0.0 |
| Revsoft | Reveal softness | Float | 0.02 | 0.02 |
| Dash | Dashes per line (0 off) | Float | 0.0 | 0.0 |
| Dashduty | Dash duty | Float | 0.5 | 0.5 |
| Dashspeed | Dash speed (dashes/s) | Float | 0.0 | 0.0 |
| Flicker | Flicker per line | Float | 0.0 | 0.0 |
| Flickerhz | Flicker rate Hz | Float | 12.0 | 12.0 |
| Maskmode | Maskmode | Menu | off | off |
| Maskop | Mask object (centre + y axis) | COMP |  |  |
| Maskcentrex | Maskcentre | XYZW | 0.0 | 0.0 |
| Maskcentrey | Maskcentre | XYZW | 0.0 | 0.0 |
| Maskcentrez | Maskcentre | XYZW | 0.0 | 0.0 |
| Maskaxisx | Maskaxis | XYZW | 1.0 | 1.0 |
| Maskaxisy | Maskaxis | XYZW | 0.0 | 0.0 |
| Maskaxisz | Maskaxis | XYZW | 0.0 | 0.0 |
| Maskradius | Mask radius | Float | 1.0 | 1.0 |
| Masksoft | Mask softness | Float | 0.2 | 0.2 |
| Maskinvert | Invert mask | Toggle | False | False |
| Occlusion | Occlusion | Menu | over | over |
| Usedepth | in_depth wired (linear eye depth in R) | Toggle | False | False |
| Occbias | Occlusion bias | Float | 0.02 | 0.02 |
| Occsoft | Occlusion softness | Float | 0.05 | 0.05 |

### Colour

| name | label | style | default | value |
|---|---|---|---|---|
| Linecolr | Linecol | RGBA | 0.25 | 0.25 |
| Linecolg | Linecol | RGBA | 1.0 | 1.0 |
| Linecolb | Linecol | RGBA | 0.4 | 0.4 |
| Linecolsrc | Linecolsrc | Menu | solid | solid |
| Linepalpos | Palette position | Float | 0.0 | 0.0 |
| Linepalspread | Palette spread (x attribute) | Float | 1.0 | 1.0 |
| Linekeep | Keep source colour | Float | 0.0 | 0.0 |
| Edgecolr | Edgecol | RGBA | 0.25 | 0.25 |
| Edgecolg | Edgecol | RGBA | 1.0 | 1.0 |
| Edgecolb | Edgecol | RGBA | 0.4 | 0.4 |
| Edgecolsrc | Edgecolsrc | Menu | solid | solid |
| Edgepalpos | Palette position | Float | 0.0 | 0.0 |
| Edgepalspread | Palette spread (x attribute) | Float | 1.0 | 1.0 |
| Edgekeep | Keep source colour | Float | 0.0 | 0.0 |
| Palsource | Palsource | Menu | neon_green | neon_green |
| Palfile | Palette file (source file) | File |  |  |
| Palmode | Palmode | Menu | cycle | cycle |
| Palinterp | Palinterp | Menu | oklab | oklab |
| Palreverse | Reverse palette | Toggle | False | False |
| Palshift | Palette shift (drive me) | Float | 0.0 | 0.0 |
| Depthnear | Depth colour near | Float | 1.0 | 1.0 |
| Depthfar | Depth colour far | Float | 10.0 | 10.0 |

### Points

| name | label | style | default | value |
|---|---|---|---|---|
| Ptstride | Texels per point (PX state 5) | Int | 1 | 1 |
| Ptcount | Points used (0 = all texels) | Int | 0 | 0 |

### Rings

| name | label | style | default | value |
|---|---|---|---|---|
| Rings | Rings on | Toggle | True | True |
| Ringcount | Rings per centre | Int | 4 | 4 |
| Ringsegs | Segments per ring | Int | 128 | 128 |
| Ringradius | Inner radius | Float | 0.5 | 0.5 |
| Ringspacing | Spacing | Float | 0.15 | 0.15 |
| Ringexpand | Expand (cycles/s, 0 = still) | Float | 0.0 | 0.0 |
| Ringspin | Spin deg/s | Float | 0.0 | 0.0 |
| Ringtilt | Tilt deg (orbits) | Float | 0.0 | 0.0 |
| Ringorbit | Orbit deg/s | Float | 0.0 | 0.0 |
| Ringface | Ringface | Menu | plane | plane |
| Ringops | Centres: objects (space separated, <= 4) | Str |  |  |
| Ringcentrex | Ringcentre | XYZW | 0.0 | 0.0 |
| Ringcentrey | Ringcentre | XYZW | 0.0 | 0.0 |
| Ringcentrez | Ringcentre | XYZW | 0.0 | 0.0 |
| Ringnormalx | Ringnormal | XYZW | 0.0 | 0.0 |
| Ringnormaly | Ringnormal | XYZW | 0.0 | 0.0 |
| Ringnormalz | Ringnormal | XYZW | 1.0 | 1.0 |
| Ringattr | Ringattr | Menu | along | along |
| Ringgain | Rings gain | Float | 1.0 | 1.0 |

### Contour

| name | label | style | default | value |
|---|---|---|---|---|
| Contour | Contour lines on | Toggle | False | False |
| Ctmax | Segments (points sampled) | Int | 32768 | 32768 |
| Ctaxis | Ctaxis | Menu | y | y |
| Ctaxisvx | Ctaxisv | XYZW | 0.0 | 0.0 |
| Ctaxisvy | Ctaxisv | XYZW | 1.0 | 1.0 |
| Ctaxisvz | Ctaxisv | XYZW | 0.0 | 0.0 |
| Ctoriginx | Ctorigin | XYZW | 0.0 | 0.0 |
| Ctoriginy | Ctorigin | XYZW | 0.0 | 0.0 |
| Ctoriginz | Ctorigin | XYZW | 0.0 | 0.0 |
| Ctspacing | Band spacing | Float | 0.05 | 0.05 |
| Ctband | Band thickness | Float | 0.01 | 0.01 |
| Ctlen | Segment length | Float | 0.03 | 0.03 |
| Ctsnap | Snap to band plane | Float | 1.0 | 1.0 |
| Ctspeed | Band scroll (bands/s) | Float | 0.0 | 0.0 |
| Ctwave | Wave amplitude | Float | 0.0 | 0.0 |
| Ctwavefreq | Wave frequency | Float | 2.0 | 2.0 |
| Ctwavespeed | Wave speed | Float | 0.5 | 0.5 |
| Cttangent | Cttangent | Menu | around | around |
| Ctfirst | First point id | Int | 0 | 0 |
| Ctcount | Point ids (0 = rest) | Int | 0 | 0 |
| Ctattr | Ctattr | Menu | index | index |
| Ctgain | Contour gain | Float | 1.0 | 1.0 |

### Trails

| name | label | style | default | value |
|---|---|---|---|---|
| Trails | Trails on | Toggle | False | False |
| Trtracks | Tracks | Int | 2048 | 2048 |
| Trsamples | Samples per track | Int | 32 | 32 |
| Trevery | Frames per sample | Int | 1 | 1 |
| Trmotion | Trmotion | Menu | flow | flow |
| Trfirst | First point id | Int | 0 | 0 |
| Trcount | Point ids (0 = rest) | Int | 0 | 0 |
| Trlife | Life s (flow) | Float | 3.0 | 3.0 |
| Trspeed | Flow speed | Float | 1.0 | 1.0 |
| Trdirx | Trdir | XYZW | 0.0 | 0.0 |
| Trdiry | Trdir | XYZW | 0.0 | 0.0 |
| Trdirz | Trdir | XYZW | -1.0 | -1.0 |
| Trcurl | Curl | Float | 0.5 | 0.5 |
| Trcurlscale | Curl scale | Float | 1.5 | 1.5 |
| Trswirl | Vortex swirl | Float | 0.0 | 0.0 |
| Trpull | Vortex pull | Float | 0.0 | 0.0 |
| Trvcam | Vortex on the camera | Toggle | False | False |
| Trvcentrex | Trvcentre | XYZW | 0.0 | 0.0 |
| Trvcentrey | Trvcentre | XYZW | 0.0 | 0.0 |
| Trvcentrez | Trvcentre | XYZW | 0.0 | 0.0 |
| Trvaxisx | Trvaxis | XYZW | 0.0 | 0.0 |
| Trvaxisy | Trvaxis | XYZW | 0.0 | 0.0 |
| Trvaxisz | Trvaxis | XYZW | 1.0 | 1.0 |
| Trjitter | Jitter (lightning) | Float | 0.0 | 0.0 |
| Trjitterhz | Jitter rate Hz | Float | 12.0 | 12.0 |
| Trmaxjump | Max jump (points) | Float | 0.5 | 0.5 |
| Trtaper | Width taper | Float | 1.0 | 1.0 |
| Trfade | Fade along | Float | 1.0 | 1.0 |
| Trattr | Trattr | Menu | index | index |
| Trgain | Trails gain | Float | 1.0 | 1.0 |

### Connect

| name | label | style | default | value |
|---|---|---|---|---|
| Connect | Connect lines on | Toggle | False | False |
| Cnpoints | Points (brute force n^2) | Int | 1024 | 1024 |
| Cnk | Neighbours per point | Int | 3 | 3 |
| Cnradius | Max distance | Float | 0.2 | 0.2 |
| Cnsub | Pieces per link (lightning) | Int | 1 | 1 |
| Cnjitter | Jitter (lightning) | Float | 0.0 | 0.0 |
| Cnjitterhz | Jitter rate Hz | Float | 12.0 | 12.0 |
| Cnfirst | First point id | Int | 0 | 0 |
| Cncount | Point ids (0 = rest) | Int | 0 | 0 |
| Cnattr | Cnattr | Menu | along | along |
| Cngain | Connect gain | Float | 1.0 | 1.0 |
| Cnindex | Cnindex | Menu | brute | brute |
| Cngrid | Index voxels per edge (x8) | Int | 32 | 32 |
| Cngridcentrex | Index box centre | XYZW | 0.0 | 0.0 |
| Cngridcentrey | Index box centre | XYZW | 0.0 | 0.0 |
| Cngridcentrez | Index box centre | XYZW | 0.0 | 0.0 |
| Cngridsize | Index box edge | Float | 4.0 | 4.0 |
| Cnpick | Cnpick | Menu | random | random |
| Cnindextop | Index points TOP (rest: static = indexed once; empty = in_points) | TOP |  |  |
| Cnistride | Index TOP texels per point (0 = Ptstride) | Int | 0 | 0 |

### Polyline

| name | label | style | default | value |
|---|---|---|---|---|
| Polyline | Polyline on | Toggle | False | False |
| Polychop | Path CHOP (tx ty tz [w]) | CHOP |  |  |
| Polyop | Place by object | COMP |  |  |
| Pomax | Max path points | Int | 4096 | 4096 |
| Poclose | Closed | Toggle | False | False |
| Pomaxgap | Pen up above gap (0 off) | Float | 0.0 | 0.0 |
| Poattr | Poattr | Menu | along | along |
| Pogain | Polyline gain | Float | 1.0 | 1.0 |

### Edges

| name | label | style | default | value |
|---|---|---|---|---|
| Edges | Edge lines on | Toggle | False | False |
| Edres | Edres | Menu | half | half |
| Edluma | Luma edges | Float | 1.0 | 1.0 |
| Edalpha | Alpha (silhouette) edges | Float | 1.0 | 1.0 |
| Eddepth | Depth edges (Usedepth) | Float | 0.0 | 0.0 |
| Edthr | Threshold | Float | 0.15 | 0.15 |
| Edsoft | Softness | Float | 0.1 | 0.1 |
| Edwidth | Width px | Float | 1.5 | 1.5 |
| Edwipe | Wipe direction deg (reveal) | Float | 0.0 | 0.0 |
| Edattr | Edattr | Menu | luma | luma |
| Edgain | Edges gain | Float | 1.0 | 1.0 |

### Info

| name | label | style | default | value |
|---|---|---|---|---|
| Status | Status | Str |  | segments 512 of 43311 |

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
| Zkm1 | Glow | Float | 0.0 | 0.24 |
| Zkm2 | Width | Float | 0.0 | 0.2 |
| Zkm3 | Energy | Float | 0.0 | 0.286 |
| Zkm4 | Chaos | Float | 0.0 | 0.0 |

## Perf

cook 186.718 ms (CPU 186.718 / GPU 2.324) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "PX_lines", "parent": "/project1/lab"}` (lands parked)
