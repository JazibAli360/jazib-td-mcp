# BL_cloud_morph

> pointcloud: BL_cloud_morph point-cloud viewer + A/B morph (live v1 in main, 26 Oct 2026, TD 2025.31550, T-89)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:07:55 from `/project1/lab/BL_cloud_morph`

`/project1/lab/BL_cloud_morph`. Shows a point cloud, or two of them (A, B), and morphs A into B: per-point eased
flight with stagger, a noise arc, colour following, size by depth, a DOF-like blur and streaks. Spec:
`docs/research/BL_gaussian_splats_pointclouds.md` section 7.2 (+ 4, 4.1, 5.1). Clean-room, our own code. The Gaussian
splat renderer is a separate COMP (`BL_splat_render`); nothing is shared or imported between them. **Splat effect
modules (30, stackable, with effectors) live in `/project1/lab/PX_pointfx` (Render splats; it reuses BL_splat_render's
shader, PSNR 73 dB vs BL with no modules): `docs/builds/px.md` "Verified live (splats)".** **No limits**
(user rule): open ranges, Count 0 = automatic, nothing capped.

**Status: LIVE v1 (26 Oct, 31550, T-89).** Verified live: build (status `travel 0.693`, load 0.20 s), errors clean
after the TDCamToProj fallback, layout ok, out1 1080x1920 alpha (banana -> sphere renders: output/pc_morph_strip.png),
CHOP = POP path (diff 0), LFO 0.25 Hz period ~4 s, BPM 120/8/2 hold 3 s fly 1 s period 8 s, cost 49k ~2.9 ms / 200k

Build doc: `docs/builds/pointcloud.md`

## Inputs / outputs

- out `out1` (outTOP) 1080x1920
- out `out_info` (outCHOP)

## Custom parameters

### Source A

| name | label | style | default | value |
|---|---|---|---|---|
| Sourcea | Source A | Menu | file | file |
| Filea | File A | File | /Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/banana.ply | /Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/SmileyPinata.spz |
| Gena | Generator A | Menu | sphere | sphere |
| Depthfilea | Depth image file A | File |  |  |
| Colourfilea | Colour image file A | File |  |  |
| Deptha | Depth TOP A (live) | TOP |  |  |
| Colora | Colour TOP A (live) | TOP |  |  |
| Upa | Up axis A (files) | Menu | y | y |
| Scalea | Scale A | Float | 1.0 | 1.0 |
| Offsetax | Offset A | XYZW | 0.0 | 0.0 |
| Offsetay | Offset A | XYZW | 0.0 | 0.0 |
| Offsetaz | Offset A | XYZW | 0.0 | 0.0 |

### Source B

| name | label | style | default | value |
|---|---|---|---|---|
| Sourceb | Source B | Menu | gen | gen |
| Fileb | File B | File |  |  |
| Genb | Generator B | Menu | sphere | sphere |
| Depthfileb | Depth image file B | File |  |  |
| Colourfileb | Colour image file B | File |  |  |
| Depthb | Depth TOP B (live) | TOP |  |  |
| Colorb | Colour TOP B (live) | TOP |  |  |
| Upb | Up axis B (files) | Menu | y | y |
| Scaleb | Scale B | Float | 1.0 | 1.0 |
| Offsetbx | Offset B | XYZW | 0.0 | 0.0 |
| Offsetby | Offset B | XYZW | 0.0 | 0.0 |
| Offsetbz | Offset B | XYZW | 0.0 | 0.0 |

### Match

| name | label | style | default | value |
|---|---|---|---|---|
| Count | Count (0 = auto) | Int | 0 | 0 |
| Match | Match | Menu | kd | kd |
| Slices | Sliced OT rounds | Int | 8 | 8 |
| Seed | Seed | Int | 0 | 0 |
| Staggermode | Stagger order | Menu | radial | radial |
| Resample | Resample | Menu | even | even |
| Outlier | Keep percentile | Float | 100.0 | 100.0 |
| Fit | Fit to unit radius | Toggle | True | True |
| Reload | Reload | Pulse | False | False |
| Status | Status | Str |  | A spz v2 228287 sh3 \| B gen sphere 228287 \| N 228287 \| travel 0.744 \| 774 ms |

### Depth

| name | label | style | default | value |
|---|---|---|---|---|
| Depthkind | Depth kind | Menu | inverse | inverse |
| Dfov | Depth camera FOV (vert deg) | Float | 60.0 | 60.0 |
| Znear | Near | Float | 1.0 | 1.0 |
| Zfar | Far | Float | 10.0 | 10.0 |
| Depthlo | Depth lo (raw) | Float | 0.0 | 0.0 |
| Depthhi | Depth hi (raw) | Float | 1.0 | 1.0 |
| Depthauto | Auto lo/hi (files: 2-98 %) | Toggle | True | True |
| Depthstep | Depth file pixel step | Int | 4 | 4 |

### Morph

| name | label | style | default | value |
|---|---|---|---|---|
| Morphmode | Morph mode | Menu | manual | manual |
| Morph | Morph A -> B | Float | 0.0 | 0.0 |
| Ease | Ease | Menu | inout | inout |
| Stagger | Stagger | Float | 0.5 | 0.5 |
| Arc | Arc (noise path) | Float | 0.3 | 0.3 |
| Colourmix | Colour follows | Float | 1.0 | 1.0 |
| Tempo | Tempo | Menu | project | project |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Beatsperswap | Beats per swap | Float | 8.0 | 8.0 |
| Morphbeats | Morph beats | Float | 2.0 | 2.0 |
| Rate | LFO Hz | Float | 0.1 | 0.1 |
| Audiochop | Audio CHOP | CHOP |  |  |
| Audiochan | Audio channel | Str | low | low |
| Audiogain | Audio gain | Float | 1.0 | 1.0 |
| Attack | Attack s | Float | 0.05 | 0.05 |
| Release | Release s | Float | 0.3 | 0.3 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Shape | Shape | Menu | disc | disc |
| Blend | Blend | Menu | add | add |
| Size | Size px | Float | 2.0 | 1.0 |
| Sizebydepth | Size by depth | Float | 0.0 | 1.0 |
| Opacity | Opacity | Float | 1.0 | 1.0 |
| Brightness | Brightness | Float | 1.0 | 1.3 |
| Tintr | Tint | RGBA | 1.0 | 1.0 |
| Tintg | Tint | RGBA | 1.0 | 1.0 |
| Tintb | Tint | RGBA | 1.0 | 1.0 |
| Tintamount | Tint amount | Float | 0.0 | 0.0 |
| Noiseamp | Drift | Float | 0.0 | 0.0 |
| Noisefreq | Noise freq | Float | 2.0 | 0.0 |
| Noisespeed | Noise speed | Float | 0.3 | 0.3 |
| Dof | DOF px per unit | Float | 0.0 | 0.0 |
| Focusdist | Focus distance | Float | 3.0 | 1.4 |
| Streak | Streak (path fraction) | Float | 0.0 | 0.0 |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Cammode | Camera | Menu | orbit | orbit |
| Camcomp | External camera | COMP |  |  |
| Orbitaz | Azimuth | Float | 0.0 | 0.0 |
| Orbitel | Elevation | Float | 10.0 | 10.0 |
| Orbitdist | Distance | Float | 3.0 | 4.8086 |
| Targetx | Target | XYZW | 0.0 | 0.0 |
| Targety | Target | XYZW | 0.0 | 0.0 |
| Targetz | Target | XYZW | 0.0 | 0.0 |
| Fov | FOV (vert deg) | Float | 45.0 | 45.0 |
| Autorbit | Orbit deg/s | Float | 6.0 | 6.0 |
| Frame | Frame both clouds | Pulse | False | False |
| Reset | Reset look | Pulse | False | False |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Resolution1 | Resolution | Int | 1080 | 1080 |
| Resolution2 | Resolution | Int | 1920 | 1920 |
| Bgcolorr | Background | RGBA | 0.0 | 0.0 |
| Bgcolorg | Background | RGBA | 0.0 | 0.0 |
| Bgcolorb | Background | RGBA | 0.0 | 0.0 |
| Bgcolora | Background | RGBA | 0.0 | 0.0 |
| Gain | Gain | Float | 1.0 | 1.0 |
| Tonemap | Tone map (additive) | Toggle | False | False |
| Outputalpha | Output alpha | Toggle | True | True |
| Premult | Premultiplied out | Toggle | True | True |
| Datapath | Instance data | Menu | chop | chop |

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
| Zkm1 | Motion | Float | 0.0 | 0.3 |
| Zkm2 | Spread | Float | 0.0 | 0.27 |
| Zkm3 | Glow | Float | 0.0 | 0.3 |
| Zkm4 | Chaos | Float | 0.0 | 0.0 |

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

## Perf

cook 1.075 ms (CPU 1.075 / GPU 3.018) summed over the 6 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BL_cloud_morph", "parent": "/project1/lab"}` (lands parked)
