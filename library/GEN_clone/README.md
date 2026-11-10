# GEN_clone

> gen_clone: GEN_clone, the G-CLONE cloner COMP (live in main, C1-C12 verified, 26 Oct 2026, TD 2025.31550)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:40 from `/project1/lab/GEN_clone`

`/project1/lab/GEN_clone` is a MoGraph / Notch / Arena-style cloner. It makes N copies of a shape: a card showing a
TOP, a box, a sphere, a torus, or any SOP. The copies are laid out in grid, radial, linear, along-a-path,
on-points or random mode, and each one is changed by step, random and noise modifiers, a per-clone time offset and the
shared effectors.
Research: `docs/research/FX0_effects_backlog.md` row 70; `docs/research/FX4_software_fx_emulation.md` 1.5 (Arena Linear / Radial / Grid
cloners), the Notch cloner list (Grid, Linear, Radial, Random, Spline, Mesh, Procedural + effectors) and 5.2 G-CLONE
(Cavalry Duplicator effector stack: Noise, Stagger, Oscillator, Time).
**Status: LIVE on b5 (31550, 26 Oct 2026), brought home into main (JazibTD_home.454.toe, 345 ops, 0 errors, parked).**
LIVE CHECKS C1-C12 ran; see "Verified live" below. `python3 -I -m unittest discover -s test -p 'test_gen_clone.py'`
passes 33 tests (~1 s): counts and texture size, a Python mirror of the clone shader for every mode, modifier, effector
action, map and time offset, the vertex transform, arc-length resampling, the ring slice rule, the live compare

Build doc: `docs/builds/gen_clone.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Clone

| name | label | style | default | value |
|---|---|---|---|---|
| Mode | Mode | Menu | grid | grid |
| Count | Count (radial / linear / path / random) | Int | 12 | 12 |
| Countx | Grid count x | Int | 5 | 5 |
| County | Grid count y | Int | 9 | 9 |
| Countz | Grid count z | Int | 1 | 1 |
| Spacex | Grid spacing | XYZW | 0.42 | 0.42 |
| Spacey | Grid spacing | XYZW | 0.42 | 0.42 |
| Spacez | Grid spacing | XYZW | 0.42 | 0.42 |
| Radius | Radial radius | Float | 1.2 | 1.2 |
| Arcstart | Arc start deg | Float | 0.0 | 0.0 |
| Arcend | Arc end deg (360 = full ring) | Float | 360.0 | 360.0 |
| Plane | Plane | Menu | xy | xy |
| Linx | Linear step offset | XYZW | 0.0 | 0.0 |
| Liny | Linear step offset | XYZW | 0.25 | 0.25 |
| Linz | Linear step offset | XYZW | 0.0 | 0.0 |
| Centre | Linear: centred on the origin | Toggle | True | True |
| Pathshape | Path shape | Menu | circle | circle |
| Pathsize | Path size (radius / half length) | Float | 1.2 | 1.2 |
| Pathturns | Spiral / helix turns | Float | 3.0 | 3.0 |
| Pathstart | Path start | Float | 0.0 | 0.0 |
| Pathend | Path end | Float | 1.0 | 1.0 |
| Pathspeed | Path travel (per s) | Float | 0.0 | 0.0 |
| Helixheight | Helix height | Float | 3.0 | 3.0 |
| Pointsource | Points from | Menu | sop | sop |
| Pointsop | Points SOP path | Str |  |  |
| Pointchop | Points CHOP path | Str |  |  |
| Pointtop | Points TOP path | Str |  |  |
| Pointstep | Every Nth point | Int | 1 | 1 |
| Pathsamples | Path resample (points path) | Int | 256 | 256 |
| Boxx | Random box size | XYZW | 2.4 | 2.4 |
| Boxy | Random box size | XYZW | 4.2 | 4.2 |
| Boxz | Random box size | XYZW | 1.0 | 1.0 |
| Seed | Seed | Int | 1 | 1 |
| Align | Align to layout (outward / tangent) | Toggle | False | False |
| Alignaxis | Axis that aligns | Menu | y | y |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Clone shape | Menu | card | card |
| Sourcesop | SOP path (Source = sop) | Str |  |  |
| Texsource | Card picture | Menu | auto | auto |
| Textop | Card TOP path | Str |  |  |
| Size | Size (uniform) | Float | 0.35 | 0.35 |
| Scalex | Scale per axis | XYZW | 1.0 | 1.0 |
| Scaley | Scale per axis | XYZW | 1.0 | 1.0 |
| Scalez | Scale per axis | XYZW | 1.0 | 1.0 |
| Colourr | Colour | RGBA | 1.0 | 1.0 |
| Colourg | Colour | RGBA | 1.0 | 1.0 |
| Colourb | Colour | RGBA | 1.0 | 1.0 |
| Alpha | Alpha | Float | 1.0 | 1.0 |
| Shading | Shading | Menu | lambert | lambert |
| Ambient | Ambient (headlight) | Float | 0.35 | 0.35 |
| Alphacut | Discard alpha below | Float | 0.0 | 0.0 |
| Blend | Blend | Menu | over | over |
| Mapmode | Map TOP | Menu | off | off |
| Maptop | Map TOP path | Str |  |  |
| Mapamount | Map amount | Float | 1.0 | 1.0 |
| Mapsize | Map size (world units across) | Float | 2.4 | 2.4 |

### Modifiers

| name | label | style | default | value |
|---|---|---|---|---|
| Steprx | Step rotate deg per clone | XYZW | 0.0 | 0.0 |
| Stepry | Step rotate deg per clone | XYZW | 0.0 | 0.0 |
| Steprz | Step rotate deg per clone | XYZW | 0.0 | 0.0 |
| Stepscale | Step scale per clone | Float | 0.0 | 0.0 |
| Stephue | Step hue (turns per clone) | Float | 0.0 | 0.0 |
| Randpx | Random position | XYZW | 0.0 | 0.0 |
| Randpy | Random position | XYZW | 0.0 | 0.0 |
| Randpz | Random position | XYZW | 0.0 | 0.0 |
| Randrx | Random rotation deg | XYZW | 0.0 | 0.0 |
| Randry | Random rotation deg | XYZW | 0.0 | 0.0 |
| Randrz | Random rotation deg | XYZW | 0.0 | 0.0 |
| Randscale | Random scale | Float | 0.0 | 0.0 |
| Randhue | Random hue (turns) | Float | 0.0 | 0.0 |
| Noisepos | Noise position | Float | 0.0 | 0.0 |
| Noiserot | Noise rotation deg | Float | 0.0 | 0.0 |
| Noisescale | Noise scale | Float | 0.0 | 0.0 |
| Noisefreq | Noise frequency (per unit) | Float | 1.0 | 1.0 |
| Noisespeed | Noise speed | Float | 0.5 | 0.5 |
| Timeoffset | Time offset (frames per step) | Float | 0.0 | 0.0 |
| Timemode | Time offset by | Menu | index | index |
| Timedepth | Card frame ring (frames) | Int | 30 | 30 |
| Ringorder | Ring slice order (LIVE CHECK C9) | Menu | newestlast | newestlast |

### Render

| name | label | style | default | value |
|---|---|---|---|---|
| Resw | Width | Int | 1080 | 1080 |
| Resh | Height | Int | 1920 | 1920 |
| Camdist | Camera distance | Float | 6.0 | 6.0 |
| Fov | Vertical FOV deg | Float | 45.0 | 45.0 |
| Camrx | Camera tilt deg | Float | 0.0 | 0.0 |
| Camry | Camera orbit deg | Float | 0.0 | 0.0 |
| Camspin | Orbit speed deg/s | Float | 0.0 | 0.0 |
| Ortho | Orthographic | Toggle | False | False |
| Orthowidth | Ortho width | Float | 3.0 | 3.0 |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |
| Bgalpha | Background alpha (0 = transparent out) | Float | 1.0 | 1.0 |
| Antialias | Antialias (4x) | Toggle | True | True |

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
| Effoffx | Offset x weight | XYZW | 0.0 | 0.0 |
| Effoffy | Offset x weight | XYZW | 0.0 | 0.0 |
| Effoffz | Offset x weight | XYZW | 0.0 | 0.0 |
| Effpush | Push (away from the effector) | Float | 0.0 | 0.0 |
| Effrotx | Rotate deg x weight | XYZW | 0.0 | 0.0 |
| Effroty | Rotate deg x weight | XYZW | 0.0 | 0.0 |
| Effrotz | Rotate deg x weight | XYZW | 0.0 | 0.0 |
| Effscale | Scale (x 1 + s w; -1 = vanish) | Float | 1.0 | 1.0 |
| Effcolourr | Tint colour | RGBA | 1.0 | 1.0 |
| Effcolourg | Tint colour | RGBA | 0.3 | 0.3 |
| Effcolourb | Tint colour | RGBA | 0.1 | 0.1 |
| Effcolourmix | Tint x weight | Float | 0.0 | 0.0 |
| Efftime | Time offset frames x weight | Float | 0.0 | 0.0 |
| Effhide | Hide at weight (0 = off) | Float | 0.0 | 0.0 |

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
| Zkm1 | Size | Float | 0.0 | 0.45 |
| Zkm2 | Chaos | Float | 0.0 | 0.0 |
| Zkm3 | Energy | Float | 0.0 | 0.17 |

## Perf

cook 132.709 ms (CPU 132.709 / GPU 1.46) summed over the 8 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GEN_clone", "parent": "/project1/lab"}` (lands parked)
