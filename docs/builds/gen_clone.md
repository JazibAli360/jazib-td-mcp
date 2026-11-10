# gen_clone: GEN_clone, the G-CLONE cloner COMP (live in main, C1-C12 verified, 26 Oct 2026, TD 2025.31550)

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
helper, a dry build on a fake TD (real effectors.py helpers) and a glslc compile of the compute shader (with and without
the effectors block) and of the MAT shaders.

## Files
| File | What |
|---|---|
| `builders/gen_clone.py` | Builder `build(parent='/project1/lab', panel=True)` (idempotent), pages, presets, the pts Script CHOP text |
| `builders/gen_clone_logic.py` | Pure logic (the COMP's `clone_logic` DAT is the same text): the uniform spec (one table for the TD expressions and the mirror), counts, the mirror (`clone_ref`, `vertex_ref`), `pts_resample`, `ring_slice`, live helpers `uniforms_of` / `compare` |
| `builders/glsl/gen_clone_layout.glsl` | `clones` compute shader: layout -> modifiers -> effectors -> map, 5 texels per clone |
| `builders/glsl/gen_clone_vert.glsl`, `gen_clone_pixel.glsl` | GLSL MAT: the instance transform from the clone texture; card picture / ring slice / headlight shading |
| `test/test_gen_clone.py` | Offline tests |

## Design (why it is built this way)
* **Instancing = a Geometry COMP with a manual instance count (N) and no instance OPs** (no POP buffers, T-124; no
  TOP-to-POP; no instance attribute par names to guess). The GLSL MAT fetches its clone from the `clones` texture by
  `TDInstanceID()`, the way PX / splat_render already render on 31550. All per-clone maths runs in one compute pass on the GPU, with no
  CPU readback (T-74).
* **5 texels per clone** (`clones`, rgba32float, CW = min(N, 1024) clones per row): 0 position xyz + uniform size,
  1 orientation quaternion (w x y z), 2 colour rgba, 3 scale xyz + time offset (frames), 4 effector weight, index,
  hidden. Hidden clones and clones past N have scale 0, so they draw no pixels.
* **Effectors via the shared list**: builders/effectors.py's own helpers (`_pars`, `_eff_in`, `_prefix`, `_buffer`,
  `_vecs`) put the Effectors page, `eff_in` / `eff_none` and the `uEffRows` texture buffer on GEN_clone, and the
  effectors block in front of the compute shader (between the adapter markers, `with_prefix`). The weight is
  `pxeConsumerW` at the clone position (selection, falloff, combine, ragged edge: all of effectors.md), so falloff
  maths is shared, not copied. `effectors.py` has the `NATIVE` entry for GEN_clone (and effectors.md a row), so
  `attach('/project1/lab/GEN_clone')` / `attach_all()` report it.
* **Time offset**: per clone `toff` frames (by index, random or distance, plus `Efftime x weight`). It delays the
  clone's modifier animation (noise time = t - toff / 60). For cards it also picks an older frame from `ring` (a
  Texture 3D TOP of Timedepth slices). The ring records only while a time offset is in use; otherwise it is 1
  slice of 8x8 and costs nothing. The slice order a GLSL MAT sees is not known offline: see `Ringorder` and C9.
* No bloat: no separate layout / effector / modifier COMPs, and no field generator. Modifiers are uniforms of one
  pass. Shapes are a SOP switch inside `geo`.

## Network (`GEN_clone`)
| Stage | Ops |
|---|---|
| Logic | `clone_logic` (module DAT), `eff_none` + `eff_in` (shared effector rows) |
| 1 Inputs | `in1` + `tex_test` (webcam clip) + `tex_sel` (Textop) -> `tex_src` -> `ring` (Texture 3D); `pts_chop` (Script CHOP: Pointsop / Pointchop, arc-length resample for a points path) -> `pts_ctop`, `pts_tsel` (Pointtop, GPU) , `pts_none` -> `pts_src`; `map_none` / `map_sel` (Maptop) -> `map_src` |
| 2 Clones | `clones` (compute, 2 wired inputs: pts_src, map_src; Arrays: uEffRows) + `clones_compute` |
| 3 Render | `geo` (`s_card` Grid SOP 2x2 uv rowcol, `s_box`, `s_sphere`, `s_torus`, `s_sop` Select SOP -> `s_sw` -> `s_norm` (unit size) -> `s_out`; instancing manual, N), `clonemat` (GLSL MAT: `clone_vert` / `clone_pixel`; samplers sClones, sTex, sRing), `target`, `cam` (orbit: Camdist, Camrx, Camry, Camspin; perspective / ortho), `render` (Resw x Resh, rgba16float, Bg + Bgalpha) |
| 4 Out | `out1` |

## Parameters
| Page | Pars |
|---|---|
| Clone | **Mode** grid / radial / linear / path / points / random; Count; Countx / y / z; Space xyz; Radius, Arcstart, Arcend (a full 360 ring spaces N evenly, an arc includes both ends), Plane xy / xz / yz; Lin xyz + Centre; Pathshape circle / line / lissajous 3:2 / spiral / helix / points, Pathsize, Pathturns, Pathstart, Pathend, Pathspeed (travel per s), Helixheight; Pointsource sop / chop / top + Pointsop / Pointchop / Pointtop, Pointstep, Pathsamples; Box xyz; Seed; **Align** + Alignaxis (the axis that points outward on radial, along the tangent on a path, along the step on linear, away from the origin on grid / points / random) |
| Look | **Source** card / box / sphere / torus / sop + Sourcesop; Texsource auto / test / top + Textop (card aspect follows the picture); Size, Scale xyz, Colour, Alpha; Shading flat / headlight + Ambient; Alphacut; Blend over / add / opaque; Mapmode off / tint / scale / both + Maptop, Mapamount, Mapsize (the map is sampled at the clone's base position xy / Mapsize + 0.5) |
| Modifiers | Step: Stepr xyz (deg per clone), Stepscale (x (1 + s i)), Stephue (turns per clone). Random: Randp xyz, Randr xyz, Randscale, Randhue (per clone hash of Seed). Noise: Noisepos, Noiserot, Noisescale, Noisefreq, Noisespeed (3D value noise at the base position, moving in time). Timeoffset (frames per step) + Timemode index / random / distance, Timedepth (ring frames), Ringorder |
| Effectors | the shared consumer page (Effon, Effselect, Effgain, Effcombine, Effradscale, Effragged, own falloff...) + Effoff xyz, Effpush (along the effector gradient), Effrot xyz, Effscale (x (1 + s w); -1 = vanish), Effcolour + Effcolourmix, Efftime (frames x w), Effhide (weight threshold, 0 = off) |
| Render | Resw / Resh (1080 x 1920), Camdist, Fov, Camrx, Camry, Camspin, Ortho + Orthowidth, Bg, Bgalpha (0 = transparent out for layering), Antialias |

Slider ranges only, no clamps (no built-in limits). Presets (zkit, full states, T-124 (1)): 1 card wall (default
5 x 9 grid), 2 ring of cards (16, aligned, time offset 2), 3 helix boxes (120, aligned to the tangent, hue step, noise
rotation), 4 noise field (9 x 16), 5 scatter (200 random, random rotation / scale / hue), 6 stagger line (24, step
rotate + shrink + time offset).

## Build (live lane, ~25 min incl. checks)
On a build TD (T-120), `lane.py add GEN_clone "<label>"` first, then:
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_clone.py').read(), ns)
ns['build']('/project1/lab')
```
Then `td_errors` recurse, `td_layout` check, `td_checkpoint`, LIVE CHECKS, `td_bring_home`, park, save. The build
reads `effectors.py` / `effectors_logic.py` / `glsl/px_common.glsl` / `glsl/eff_consumer.glsl` (not edited). It works
without `/project1/effectors` (eff_none: the effector weight is 0).

## LIVE CHECKS (expected numbers)
`compare` = `op('/project1/lab/GEN_clone/clone_logic').module.compare(op('/project1/lab/GEN_clone'))` returns
(max diff, clone, texel, N). It does a readback, so run it in its own exec (T-117). Set Noisespeed / Pathspeed / Camspin
to 0 for compare, because the uniform time is read one frame after the cook.

| # | Check | Expected |
|---|---|---|
| C1 | Build, `td_errors` recurse | 0 errors: `clones` compiles (with the effectors block), `clonemat` compiles (vertex + pixel). TD names glslc cannot know: `uv[0]`, `TDNormal`, `TDDeform(vec3)`, `TDDeformNorm`, `TDWritePickingValues` (cloth / prox_mat use them on 31550). sampler3D bound to a texture3dTOP: if TD rejects it, record (LEARNINGS) and switch `ring` to `2darray` + `sampler2DArray` |
| C2 | Default (grid 5 x 9, Source box, Shading flat, Colour white, bg black), Ortho on, Orthowidth 3, Camdist 6 | `geo.par.numinstances` 45; `clones` 225 x 1; render: 45 white squares of 126 px (0.35 x 360 px/unit) at x = 540 + 151.2 (ix - 2), y = 960 + 151.2 (iy - 4) from the bottom; white coverage 0.344 +- 0.01. If the squares come out 1.78x smaller, Orthowidth is the vertical extent on 31550: record it |
| C3 | `compare` on the default | max diff < 1e-5 (float32 vs float64), N 45 |
| C4 | Mode radial Count 16 Align 1; Mode linear; Mode path (circle, helix); Mode random Count 200 | `compare` < 1e-4 each (sin / cos in float32) |
| C5 | Modifiers: Steprz 10, Stepscale 0.05, Randp 0.2, Randhue 0.3, Noisepos 0.2 (Noisespeed 0) | `compare` < 1e-4 (hash and value-noise mirror: same uint maths) |
| C6 | Points: Pointsource sop = a Sphere SOP (`/project1/lab/GEN_clone/geo/s_sphere`, mesh), Mode points | N = its point count (`count_of`); `compare(c, pts=[...points...])` < 1e-5; Pointsource top = a Noise TOP 64 x 64 -> N 4096, no Script CHOP cook (`pts_chop` cook count flat) |
| C7 | Effectors: `/project1/effectors` sphere1 at the origin (radius 0.5), Effon, Effscale -1 | clone 22 (origin) texel 4 weight = `effectors_logic.ref_weight` at (0, 0, 0) (1.0 x gain for a sphere centre); it vanishes (texel 0 w = 0); clones beyond the radius keep weight 0; moving sphere1 moves the hole; no recompile when the list changes |
| C8 | Source card, Texsource test | each clone shows the webcam clip; card aspect = 1920 / 1080 (uR.w 1.778); Blend over: overlapping cards composite premultiplied (no dark fringes) |
| C9 | Ring order: Source card, `Textop` = a Constant TOP whose colour r = `(absTime.frame % 30) / 30`, Timeoffset 5, Timedepth 30 | clone k shows r = ((frame - 5k) mod 30) / 30 with Ringorder `newestlast`; if clone 0 shows the oldest frame instead, set `newestfirst` as the default and record (LEARNINGS). If neither fits (a circular ring), note it: the shader then needs the write index (fx_time_ring stamp pattern) |
| C10 | Source sop: Sourcesop = any SOP (e.g. a Text SOP or a Font SOP) | clones render that SOP; s_norm scale 1 (the SOP's own units) |
| C11 | Path points: Pathshape points, Pointsource chop = a Noise CHOP 32 samples tx ty tz, Count 64, Align | clones evenly spaced along the polyline (arc-length resample, Pathsamples 256), aligned to its tangent |
| C12 | Cost (pane elsewhere, other COMPs parked) | report `clones` GPU, `render` GPU + CPU, CPU of the expressions, project fps at: 45 boxes, 45 cards (test clip), 1 000 boxes, 10 000 boxes, 10 000 cards, 50 000 boxes, and 10 000 boxes with Effon (4 effectors) |

## Verified live (b5, TD 2025.31550, 26 Oct 2026; 6 TDs on the Mac, other lab COMPs parked)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
| # | Result |
|---|---|
| C1 | 0 errors: `clones` (with the effectors block) and `clonemat` (vertex + pixel, `sampler3D sRing` on the Texture 3D TOP) compile on 31550. Fixed on the way: the Switch SOP's par is `input`, not `index` (the first build stopped there; test pins it) |
| C2 | grid 5 x 9, box, flat, ortho 3, Camdist 6: numinstances 45, clones 225 x 1; 45 squares of 126 px at x 175-300 / 326-451 / 477-602 / 628-753 / 779-904 (centres 151 px apart, middle 539.5), rows 292..1627 (middle 959.5); white coverage 0.3445. **Orthowidth is the horizontal extent** (360 px / unit at 1080 wide) |
| C3 | compare default: 5.2e-8, N 45 |
| C4 | radial 16 aligned 4.5e-7; linear 6e-9 (aligned too); path circle 7.6e-6, helix 3.0e-6, lissajous 5.0e-6, spiral 2.8e-6 (aligned); random 200 1.9e-7; grid 5 x 9 x 3 aligned 1.1e-7 |
| C5 | grid with Steprz 10, Stepscale 0.05, Randp 0.2, Randhue 0.3, Noisepos 0.2: 3.9e-7; random 200 with Randr 30, Randscale 0.5, Noiserot 0.5, Noisescale 0.3, Stephue 0.01: 1.9e-6 |
| C6 | points from `geo/s_sphere`: N 722 = its point count, compare 6e-9; Pointsource top = 64 x 64 Noise TOP: N 4096, clones 5120 x 4, compare vs the noise pixels 6e-9, `pts_chop` cooks flat (14 -> 14) |
| C7 | (effectors built on b5 for the check, removed after) sphere1 at the origin, Effselect sphere1, Effon, Effscale -1: weights = `effectors_logic.ref_weight` within 1.5e-7 over all 45 clones (centre 1.0, (-0.42, -0.42) 0.907, far 0); size 0.35 x (1 - w) (vanish at w 1); sphere1 to x 0.84 moves the hole (row iy 4: 0, 0, 0.24, 1, 1); compute text unchanged (no recompile). Trap: see below |
| C8 | card + test clip: uR.w 1.7778 (1920 / 1080), every clone shows the clip, overlapping cards composite cleanly (capture) |
| C9 | Ring order **`newestlast` is right** (the default stays): with Timeoffset 1 the age (r0 - rk) x 30 rises with k (0, 1, 3, 5, 10, ...); `newestfirst` makes it fall. Not circular. Ages count ring cooks, not absTime frames: b5 cooked ~46-50 frames/s under load, so ages jump 1-5 frames per slice (the doc's exact (frame - 5k) holds only at a full 60) |
| C10 | Source sop = a Torus SOP (800 points): clones render it, s_norm scale 1 |
| C11 | path points from a Noise CHOP (32 samples tx ty tz), Pathsamples 256, Count 64, Align: pts_chop 256 samples, compare 1.25e-4 (quaternion texel, float32 tangents) |
| C12 | below |

**Cost (C12), median over 90 frames, 1080 x 1920 rgba16float, perspective, lambert, AA on, Noisespeed 0.5 (clones
recompute every frame), ms:**
| Case | clones GPU | clones CPU | render GPU | render CPU | real fps |
|---|---|---|---|---|---|
| 45 boxes | 0.14 | 0.24 | 0.21 | 1.73 | 52.5 |
| 45 cards (test clip) | 0.12 | 0.23 | 0.36 | 1.56 | 51.5 |
| 1k boxes | 0.13 | 0.24 | 0.31 | 1.81 | 57.3 |
| 10k boxes | 0.23 | 0.24 | 0.83 | 1.79 | 56.1 |
| 10k cards (test clip) | 0.16 | 0.22 | 0.80 | 1.56 | 55.6 |
| 50k boxes | 0.18 | 0.20 | 2.48 | 1.33 | 60.2 |
| 10k boxes, Effon (4 effectors) | 0.13 | 0.20 | 1.57 | 1.37 | 59.5 |
`geo` CPU 0.09-0.16. Real fps = cooks/s of a Constant TOP reading absTime.frame; b5 ran 50-53 with nothing cooking
(load average 47-65 on the Mac), so fps here is the machine, not GEN_clone. The Render TOP CPU (1.3-1.8 ms) is the
fixed per-render floor under Rosetta (T-150). Single numbers vary ~1.5x run to run (shared GPU); the effectors pass
cost no measurable extra in `clones`. Under 3 ms up to 10k clones; 50k boxes ~4 ms (render GPU bound).
**Effector trap on a TD without /project1/effectors at build time:** `eff_in`'s `chops` and the `uEffSel` / `uEffIds`
expressions (`... if op('/project1/effectors/...') is not None else ...`) were evaluated once with the list missing, never
read `Effselect` or the list, so they kept the empty values after the list was built (LEARNINGS T-158). Main has the
list, so main is not affected; on another TD, build /project1/effectors first or re-set those expressions.

## Estimated cost (offline guess, superseded by "Verified live")
* `clones`: one thread per clone. Effectors off: under 0.05 ms up to ~10k clones. Effectors on: about N x the
  selected effector count x one falloff (PX measured 65k particles x 2 effectors = 0.43 ms), so ~0.1-0.3 ms at 10k.
* Render at 1080 x 1920: 45 cards 0.2-0.5 ms (blend over full-screen cards is fill-bound); 1k boxes ~0.3 ms;
  10k boxes ~0.6-1.2 ms; 10k default spheres (several hundred triangles each) 2-4 ms, so use box / card / a low-poly
  SOP for big counts. Per-instance cost is 4 texel fetches in the vertex shader (PX: instanced quads are
  triangle-setup bound past ~100k, T-84 / LEARNINGS (6)).
* CPU: ~90 uniform expressions plus `count_of` calls, ~0.2-0.4 ms per frame (est.). If C12 shows more, move the
  uniforms into one Script CHOP -> uniform array (the fx_retro codes pattern). The Script CHOP `pts_chop` cooks only
  when its source changes; SOPs over ~20k points cost Python time per change, so use Pointsource top for those.
* Ring (cards with a time offset): Timedepth x the picture size of VRAM, e.g. 30 x 1920 x 1080 x 4 B = 250 MB at
  8-bit. Lower Timedepth or feed a smaller Textop for big rings.
