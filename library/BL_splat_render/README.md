# BL_splat_render

v0.2.1 - TD 2025.31550 - exported 2026-10-29 00:08:00 from `/project1/lab/BL_splat_render`

## Inputs / outputs

- out `out1` (outTOP) 1080x1920
- out `out_info` (outCHOP)

## Custom parameters

### Source

| name | label | style | default | value |
|---|---|---|---|---|
| File | Splat file | File | /Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/SmileyPinata.spz | /Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/SmileyPinata.spz |
| Format | Format | Menu | auto | auto |
| Reload | Reload | Pulse | False | False |
| Maxsplats | Max splats (0 = all) | Int | 0 | 209424 |
| Thinstep | Thin step | Int | 1 | 1 |
| Thinrandom | Thin random | Float | 0.0 | 0.188 |
| Opacitycull | Opacity cull | Float | 0.0 | 0.0 |
| Shdegree | SH degree | Menu | 1 | 1 |
| Coordfix | Coord fix | Menu | auto | auto |
| Pointscale | Point-cloud splat size | Float | 0.01 | 0.01 |
| Cropcenterx | Crop centre | XYZW | 0.0 | 0.0 |
| Cropcentery | Crop centre | XYZW | 0.0 | 0.0 |
| Cropcenterz | Crop centre | XYZW | 0.0 | 0.0 |
| Cropsizex | Crop size (0 = off) | XYZW | 0.0 | 0.0 |
| Cropsizey | Crop size (0 = off) | XYZW | 0.0 | 0.0 |
| Cropsizez | Crop size (0 = off) | XYZW | 0.0 | 0.0 |
| Cropradius | Crop radius (0 = off) | Float | 0.0 | 0.0 |
| Autoframe | Frame camera on load | Toggle | True | True |
| Status | Status | Str |  | spz 185,267 of 228,287 splats, load 130 ms, radius 0.50 |
| Reset | Reset look/camera | Pulse | False | False |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Cammode | Camera | Menu | orbit | orbit |
| Camcomp | External camera | COMP |  |  |
| Orbitaz | Azimuth | Float | 0.0 | -39.0 |
| Orbitel | Elevation | Float | 10.0 | 11.7 |
| Orbitdist | Distance | Float | 3.0 | 1.0997 |
| Targetx | Target | XYZW | 0.0 | 0.010498046875 |
| Targety | Target | XYZW | 0.0 | -0.039306640625 |
| Targetz | Target | XYZW | 0.0 | -0.028076171875 |
| Fov | FOV (vertical deg) | Float | 45.0 | 55.5 |
| Autorbit | Orbit deg/s | Float | 10.0 | 17.3 |
| Orbitsync | Orbit sync | Menu | none | none |
| Bpm | BPM | Float | 120.0 | 124.8 |
| Beatsperrev | Beats per rev | Float | 32.0 | 36.1 |
| Frame | Frame splats | Pulse | False | False |

### Splat

| name | label | style | default | value |
|---|---|---|---|---|
| Scalemult | Scale | Float | 1.0 | 0.61 |
| Opacitygain | Opacity | Float | 1.0 | 1.106 |
| Alphathreshold | Alpha thr | Float | 0.015 | 0.0 |
| Lowpass | Low-pass px2 | Float | 0.3 | 0.95 |
| Brightness | Brightness | Float | 1.0 | 1.15 |
| Gamma | Gamma | Float | 1.0 | 1.27 |
| Srgbtolinear | sRGB to linear | Toggle | False | True |
| Pointmix | Point mix | Float | 0.0 | 0.0 |
| Pointsize | Point px | Float | 3.0 | 3.0 |

### Sort

| name | label | style | default | value |
|---|---|---|---|---|
| Sortmode | Sort mode | Menu | sortpop | sortpop |
| Sorteveryn | Every N frames (0 = off) | Int | 0 | 14 |
| Sortmovedeg | Re-sort after deg | Float | 1.0 | 5.92 |
| Sortnow | Sort now | Pulse | False | False |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Dissolve | Dissolve | Float | 0.0 | 0.0 |
| Dissolveseed | Dissolve seed | Float | 0.0 | 69.2 |
| Noiseamp | Noise amp | Float | 0.0 | 0.0 |
| Noisefreq | Noise freq | Float | 2.0 | 2.12 |
| Noisespeed | Noise speed | Float | 0.3 | 0.28 |
| Explode | Explode | Float | 0.0 | 0.0 |
| Reveal | Reveal | Float | 1.0 | 1.0 |
| Beatpulse | Beat pulse | Float | 0.0 | 0.0 |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiochop | Audio CHOP | CHOP |  |  |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Resolution1 | Resolution | Int | 1080 | 1080 |
| Resolution2 | Resolution | Int | 1920 | 1920 |
| Bgtop | Background TOP | TOP |  |  |
| Bgcolorr | Background colour | RGBA | 0.0 | 0.0 |
| Bgcolorg | Background colour | RGBA | 0.0 | 0.0 |
| Bgcolorb | Background colour | RGBA | 0.0 | 0.0 |
| Bgcolora | Background colour | RGBA | 0.0 | 0.0 |
| Premult | Premultiplied out | Toggle | True | True |
| Outputalpha | Output alpha | Toggle | True | True |
| Renderscale | Render scale | Menu | full | full |

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
| Zkm1 | Motion | Float | 0.0 | 0.333 |
| Zkm2 | Glow | Float | 0.0 | 0.333 |
| Zkm3 | Chaos | Float | 0.0 | 0.0 |
| Zkm4 | Size | Float | 0.0 | 0.333 |

### Effectors

| name | label | style | default | value |
|---|---|---|---|---|
| Effon | Effectors on (/project1/effectors) | Toggle | False | False |
| Effselect | Use effectors (all / names / #tags) | StrMenu | all | all |
| Effgain | Weight gain | Float | 1.0 | 1.0 |
| Effcombine | Combine | Menu | max | max |
| Effradscale | Radius scale | Float | 1.0 | 1.0 |
| Effragged | Ragged edge | Float | 0.0 | 0.0 |
| Effraggedfreq | Ragged freq | Float | 4.0 | 4.0 |
| Effoverride | Own falloff (ignore per-effector) | Toggle | False | False |
| Effradius | Own radius | Float | 0.5 | 0.5 |
| Effexp | Own exponent | Float | 1.0 | 1.0 |
| Effshape | Own shape | Menu | smooth | smooth |
| Effpush | Push (units) | Float | 0.3 | 0.3 |
| Effdissolve | Dissolve (+ near / - reveal near) | Float | 0.0 | 0.0 |
| Effgrow | Scale near (x 1 + gain w) | Float | 0.0 | 0.0 |
| Effdust | Dust (per point thresholds) | Toggle | True | True |
| Effdir | Push direction | Menu | outward | outward |
| Splatfx | Splat FX modules | Str |  | /project1/lab/PX_pointfx (Render splats) |

### Geo

| name | label | style | default | value |
|---|---|---|---|---|
| Geoon | Geometry in the scene | Toggle | False | False |
| Geocomps | Geometry COMPs (paths / patterns) | Str |  |  |
| Geolights | Lights (paths, #tag; #light = all in /project1/effectors) | Str | #light | #light |
| Geokey | Built-in key light | Toggle | True | True |
| Georelight | Relight splats (light effectors) | Float | 0.0 | 0.0 |
| Geoambient | Splat ambient (relight) | Float | 0.25 | 0.25 |
| Geolightmode | Splat light mode | Menu | halflambert | halflambert |
| Geodepthbias | Splat depth bias (world) | Float | 0.0 | 0.0 |
| Geoenv | Scene environment (chrome) | Toggle | False | False |
| Geoenvgeo | Environment captures (geometry) | Str | draw | draw |
| Geoenvcentrex | Environment centre (chrome object) | XYZW | 0.0 | 0.0 |
| Geoenvcentrey | Environment centre (chrome object) | XYZW | 0.0 | 0.0 |
| Geoenvcentrez | Environment centre (chrome object) | XYZW | 0.0 | 0.0 |
| Geoenvres | Environment cube px | Int | 256 | 256 |
| Geoenveveryn | Environment every N frames | Int | 4 | 4 |
| Geoenvdimmer | Environment dimmer | Float | 1.0 | 1.0 |

## Perf

cook 1.015 ms (CPU 1.015 / GPU 2.065) summed over the 6 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BL_splat_render", "parent": "/project1/lab"}` (lands parked)
