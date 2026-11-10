# pointcloud: BL_cloud_morph point-cloud viewer + A/B morph (live v1 in main, 26 Oct 2026, TD 2025.31550, T-89)

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
~3.7 ms (over the 3 ms aim), project 59.8 fps. Still unverified: steps 3-4 numeric ends/centroid, 7 depth TOP, 8 shapes
/ blends, 9 Count x20 memory + rebuild with window open, 1M, three COMPs, tox save. Earlier text: Every claim that needs TD is marked `LIVE CHECK:` and is
unverified until a live lane records it (numbers -> this file, new TD facts -> `LEARNINGS.md`).

## Files
| File | What |
|---|---|
| `builders/pointcloud.py` | builder: `build(parent_path='/project1/lab', name='BL_cloud_morph', panel=True)` |
| `builders/pointcloud_logic.py` | pure logic, no `td` (copied into `pointcloud_logic`): loaders, depth unprojection, generators, fit, resample, k-d / Morton / sliced-OT matching, morph maths, clock |
| `builders/pointcloud_rt.py` | TD runtime (copied into `pc_rt`): load cache, Script CHOP callbacks, debounced reload, depth-TOP uniforms |
| `builders/glsl/pointcloud_vertex.glsl` | GLSL MAT vertex: morph, depth-TOP unprojection, sizes, streaks (`pc_vertex`) |
| `builders/glsl/pointcloud_pixel.glsl` | GLSL MAT pixel: disc / soft / square / ring / streak, add / over / opaque (`pc_pixel`) |
| `builders/glsl/pointcloud_post.glsl` | ONE compute pass: gain, tone map, background, alpha (`post_compute`) |
| `test/test_pointcloud.py` | 48 offline tests: `python3 -I -m unittest discover -s test -p 'test_pointcloud.py'` (green, 1.0 s) |

All three shaders compile with `glslc` (OpenGL target) against stubs of the TD functions they call (offline syntax and
type check only; TD's own compile is a LIVE CHECK).

## Build (live lane, ~15 min)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pointcloud.py').read(), ns)
ns['build']('/project1/lab')
```
Idempotent (ops reused by name, wires/texts/pars re-set, custom par values kept). T-70 safe: closes its own
`controls_window` first, destroys only through `safe_destroy`, zkit refreshes the panel in place, never moves the
network pane. No functions in storage (T-67). Never reads TOP pixels (T-74): a depth TOP's `width`/`height` only.
Only single-pass GLSL MAT + one compute GLSL TOP (T-46/T-47). The first load runs synchronously inside `build()`
(default ~0.15 s offline on arm64 numpy; Rosetta slower).

## Sources (per side A / B: `Sourcea` / `Sourceb`)
| Source | What | Notes |
|---|---|---|
| `file` | `.ply` (ascii / binary LE / BE; rgb uchar or float, or 3DGS `f_dc_*` + `opacity`), `.xyz .pts .txt .csv` (header names used; no header + >= 6 cols = xyz rgb), `.obj` (`v x y z [r g b]`), `.splat` and `.spz` v2/v3 (centres + colour + alpha) | SPZ 4 (ZSTD) and SPZ v1 refused with a clear Status |
| `gen` | sphere (Fibonacci), grid cube, torus, cube surface, helix, gaussian blob, plane, ring, galaxy spiral | N = Count, else the other side's count, else 100 000 |
| `depthfile` | depth image file -> cloud (`Depthstep` pixel step), optional colour image file | `.npy .pfm .pgm` offline; `.png .jpg .exr .tif` need cv2 in TD's Python (research says 4.11 is there; LIVE CHECK) |
| `depthtex` | **live depth TOP** (e.g. the camera_bridge Depth Anything map) + optional colour TOP, unprojected **on the GPU** in the vertex shader from a uv grid of N points | lo/hi from `Depthlo`/`Depthhi` (raw TOP values); P on the CPU is a mid-depth proxy plane used for matching only |

Depth maths (`unproject_uv`, mirrored in `texSide()`): `dn = (d - lo)/(hi - lo)` clamped; inverse kind (Depth
Anything, relative inverse depth): `z = zfar/(1 + dn*(zfar/znear - 1))`; depth kind: `z = znear + dn*(zfar - znear)`;
`x = (u-0.5)*2*tan(fov/2)*aspect*z`, `y = (v-0.5)*2*tan(fov/2)*z`, point = `(x, y, -z)`. uv has v up (TD textures);
file arrays are rows top-first and are flipped.

Per side: `Up` axis (files only: y / z / -y / -z), `Scale`, `Offset`. Shared: `Outlier` (keep percentile of the
distance from the median, 100 = all), `Fit` (centre + unit radius), `Count`, `Match`, `Slices`, `Seed`,
`Staggermode`, `Resample`.

### Sample assets (already on disk) and the numbers to expect (offline, arm64 numpy 2.5.2; load+match ms)
| A | B | Pars | A / B / N | travel (mean pair distance, unit fit) | ms |
|---|---|---|---|---|---|
| `TD 2.app/.../Samples/PointClouds/banana.ply` (default) | gen sphere (default) | Count 0, kd | 49 106 / 49 106 / 49 106 | 0.693 | 155 |
| same | same | Match morton | same | 1.062 | 61 |
| `Samples/PointClouds/SmileyPinata.spz` | gen torus | Count 0 | 228 287 / 228 287 / 228 287 | 0.625 | 610 |
| `research_src/BL_gaussian_splats_pointclouds/samples/nike.splat` (Up -y) | banana.ply | Count 200000 | 270 491 / 49 106 / 200 000 | 0.367 | 532 |
| `research_src/.../samples/hornedlizard.spz` **Outlier 90** (7 % of it is a +-200 shell) | gen spiral | Count 300000 | 707 609 (of 786 233) / 300 000 / 300 000 | 0.461 | 1363 |
| banana.ply | depthtex (no TOP -> `blank`) | Count 100000 | 49 106 / 100 000 / 100 000 | 0.291 | 222 |
Also: `Samples/PointClouds/sphere.xyz` = 812 points, no colour (its U V Nx columns are not colours);
`bananaNorm.ply` = 49 106. Matching cost: k-d 1 M x 1 M = 3.5 s offline (load-time only).

## Morph
- Per point: `e = ease(clamp(m*(1+Stagger) - delay*Stagger))`, `delay` 0..1 from `Staggermode` (radial = centre
  first, height = bottom first, noise, index). So m = 0 is exactly A and m = 1 exactly B for any stagger.
- `P = mix(A, B, e) + noise3(A*Noisefreq + seed, t*Noisespeed) * (Arc*sin(pi e) + Drift)`; colour = `mix(Ca, Cb,
  e*Colourfollows)`, then Tint / Brightness / Opacity.
- `Morphmode`: manual (`Morph`), BPM (ping-pong: hold `Beatsperswap - Morphbeats` beats, fly `Morphbeats`, period
  2 x Beatsperswap; tempo = project or `Bpm`), LFO (`Rate` Hz, cosine 0..1), audio (`Audiochop` / `Audiochan` max per
  frame, attack/release follower x `Audiogain`; any value, no clamp: the shader's ease clamps).
- Matching (load time, numpy): `kd` (default; balanced k-d split pairs, exact for a moved copy), `sliced` (`Slices`
  rounds of sliced-OT flow of A toward B, then k-d pairs along random directions), `morton` (rank along each cloud's
  Z-order curve: fastest, loosest), `index`, `random`.
- Look: Shape (disc / soft / square / ring / streak = stretched along the projected A -> B path by `Streak` x
  sin(pi e)), Blend (additive / over (unsorted) / opaque with depth test), Size px at the orbit distance, Size by depth
  (0 = constant px, 1 = perspective), DOF (`Dof` px per unit away from `Focusdist`, alpha scaled by area so energy
  stays), Tint + amount. No sorting is needed: add and opaque are order independent; over is unsorted by design.
- Camera: internal orbit (`Orbitaz/el/dist`, `Target`, `Fov`, `Autorbit` deg/s) through `cam` (look-at `target`), or
  an external Camera COMP. `Frame` pulse fits both clouds (default: Orbitdist 4.81, Target 0,0,0). `Reset` resets the
  look pars.

## Parameters (custom pages; the zkit panel shows Morph, Look, Camera; pulse `Opencontrols`)
| Page | Pars |
|---|---|
| Source A / Source B | Source, File, Generator, Depth image file, Colour image file, Depth TOP (live), Colour TOP (live), Up axis, Scale, Offset |
| Match | Count (0 = auto), Match, Slices, Seed, Staggermode, Resample (even / random), Outlier (keep percentile), Fit, Reload, Status (read-only) |
| Depth | Depthkind (inverse / depth), Dfov, Znear, Zfar, Depthlo, Depthhi, Depthauto (files: 2-98 % percentiles), Depthstep |
| Morph | Morphmode, Morph, Ease (linear / in / out / in-out / sine), Stagger, Arc, Colourmix, Tempo, Bpm, Beatsperswap, Morphbeats, Rate, Audiochop, Audiochan, Audiogain, Attack, Release |
| Look | Shape, Blend, Size, Sizebydepth, Opacity, Brightness, Tint, Tintamount, Noiseamp (Drift), Noisefreq, Noisespeed, Dof, Focusdist, Streak |
| Camera | Cammode, Camcomp, Orbitaz, Orbitel, Orbitdist, Target, Fov, Autorbit, Frame, Reset |
| Output | Resolution (1080 x 1920), Bgcolor (rgba, 0 = transparent), Gain, Tonemap, Outputalpha, Premult, Datapath (chop / pop) |
Load pars (Source A/B, Match, Depth pages) reload after a 6-frame debounce (Parameter Execute -> Execute DAT
`frame_exec`, never inside a cook).

## Network (stages, L to R)
Controls (`controls`, `controls_window`, `par_exec`, `frame_exec`, `pointcloud_logic`, `pc_rt`) | 1 Load + match
(`cloud_data` Script CHOP: one sample per point, 20 channels `ax ay az dl | bx by bz sd | ar ag ab aa | br bg bb ba |
ua va ub vb`; `to_pop` CHOP to POP -> `cloud_pop` for Datapath pop) | 2 Clock (`engine` Script CHOP per frame: morph
beat bpm level az camx camy camz t) | 3 Draw + render (`draw` Geometry COMP: rectangle SOP quad, instancing from
`cloud_data` (or `cloud_pop`), 5 custom instance slots; `pcmat` GLSL MAT with `pc_vertex`/`pc_pixel`, samplers
sDepthA sColA sDepthB sColB (-> `blank` when unset); `target`, `cam`, `render` 16F) | 4 Output (`post` compute GLSL ->
`out1`; `info` + `engine` -> `info_merge` -> `out_info`). Out = `out1` (image) and `out_info` (data) only.

## Live verification (in this order; record numbers here, TD facts in LEARNINGS)
Before: `td_status`; un-park only this COMP (CLAUDE.md "Park idle COMPs"); one TOP readback at a time, >= 2 frames
after any TOP change (T-74).
1. **Build** (command above). Expected reply `status` = `A ply ascii 49106 colour rgb | B gen sphere 49106 | N 49106 |
   travel 0.693 | <ms>`. `td_errors /project1/lab/BL_cloud_morph` clean; `td_layout check` ok (no intruders / unboxed
   / box overlaps). LIVE CHECK: load ms under Rosetta (offline arm64 155 ms; expect <= 0.5 s).
2. **Picture**: view `out1`: banana in colour, 1080 x 1920, alpha real (transparent bg). Morph 1 -> sphere, Morph 0.5
   -> half-way cloud with arc noise. LIVE CHECK: GLSL MAT compiles on Vulkan/MoltenVK (TDCamToProj, TDCheckDiscard,
   TDSimplexNoise, `TDInstanceCustomAttrib0..4(id)`, textureLod in the vertex stage), points face the camera and sit
   where the CHOP says.
3. **L2 ends**: read `out_info` and the instance CHOP, not pixels: with Morph 0 and 1 compare the shader maths
   offline (`point_morph` = 0 / 1 exactly). Pixel check only via one delayed readback of `out1` (Shape square, Size 1,
   Blend opaque, Count 1000, Morph 0 vs a render of A alone) -> identical image (max abs diff < 1/255).
4. **L3 mid centroid**: offline expected centroid of A and B for the default pair: A (-0.0759, -0.1653, -0.0061),
   B (0, 0, 0), mid (-0.0379, -0.0826, -0.0031) (Arc 0, Drift 0, Stagger 0). LIVE CHECK via Datapath pop + a
   throwaway POP to TOP readback is optional (CHOP path has no GPU positions to read).
5. **Datapath pop**: switch to `pop`, the picture must not change. LIVE CHECK: POP instancing with custom
   attributes `Pa(0)` style names on 31550; whether `instance<N>customop` blank defaults to `instanceop` (the builder
   sets it explicitly).
6. **Modes**: BPM 120, Beatsperswap 8, Morphbeats 2 -> morph 0 for 3 s, flies 1 s, holds 3 s, back 1 s (period 8 s)
   from `out_info` `morph`; LFO 0.25 Hz -> period 4 s; audio with `/project1/audio/analysis` low (if built) follows.
7. **Depth TOP**: point Sourceb = depthtex, Depthb = a Ramp TOP (vertical, 0..1) as a synthetic depth: L1 = a tilted
   plane; with Depthkind depth, Znear 1, Zfar 10 the top row sits at z = -10 (before fit), bottom at -1. Then the
   camera_bridge depth map from `media/webcam/webcam_ref_5s.mp4` (td-port helper kind 1; never the live camera)
   with Colorb = the movie TOP. LIVE CHECK: a Ramp/Movie TOP referenced by a MAT sampler from outside the COMP cooks.
8. **Shapes / blends / DOF / streak** each once (soft + add, ring + over, disc + opaque, Dof 4 Focus 3, Streak 0.5 at
   Morph 0.5).
9. **Count change x20** (Count 50k <-> 200k) with `td_perf` memory: flat (L6). Rebuild with the controls window open:
   no crash (T-70 pattern).
10. **Perf** (fps target below) then park the COMP again; ask the main session to save + `td_tox_save` to
    `projects/lab_tox/BL_cloud_morph_v01.tox` (T-71: agents never save).

### fps target (60 fps project rule: whole project 16.6 ms, this COMP <= 3 ms)
| Case | Target (to measure, not a claim) |
|---|---|
| default 49k disc 2 px, add, 1080x1920 | 60 fps, COMP <= 1.5 ms (Render GPU + engine 0.2 ms CPU + post) |
| 200k disc 2 px | 60 fps, COMP <= 3 ms |
| 300k + Dof 4 or Streak 0.5 (overdraw) | >= 30 fps; if not, lower Size/Count and say so |
| 1M (lizard, Count 1000000) | measure; expect < 30 fps; load 3.5 s+ (k-d) or use Match morton |
| 3 clouds x 200k (three COMPs, spec L4) | 30 fps |
Engine cooks every frame (one Script CHOP, ~9 channels); `cloud_data` cooks only on load. Measure with viewers on
(user rule) and the network pane on this COMP, and once with it elsewhere (T-73: the pane is a hidden cost).

## LIVE CHECK list (all unverified on TD 2025.31550)
- GLSL MAT compile: `TDCamToProj`, `TDCheckDiscard`, `TDSimplexNoise(vec4)`, `TDInstanceCustomAttribN(int)`,
  `uTDMats[TDCameraIndex()].cam`, vertex-stage `textureLod`, `inout vec3` with a swizzled argument. Fallback for
  TDCamToProj: `uTDMats[ci].proj * vc`.
- CHOP instancing: `instanceop` expression returning `'../cloud_data'`, `instancecountmode oplength` = 49 106 instances,
  custom slots from CHOP channel names after `geo.seq.instance.numBlocks = 5`; `instancetx/ty/tz` set to ax/ay/az for
  bounds only (the shader ignores them).
- POP route: `choptoPOP` attribute blocks (`attr<i>chanscope/name custom/customname/type/numcomps`), `surftype points`,
  `chanscope 'ax ay az'` + `attrscope P`; instancing from `cloud_pop` with `Pa(0)` names.
- GLSL MAT: `seq.vec.numBlocks = 15`, `seq.sampler.numBlocks = 4`, sampler par expression returning an OP,
  `destblend`/`depthtest` driven by expressions; Render TOP alpha with `bgcolora 0` (T-15).
- `cam.par.lookat = 'target'` with expression-driven position; Vulkan Y flip vs our NDC offsets (symmetric quads do
  not care; streak direction is computed in the same NDC space).
- Script CHOP `copyNumpyArray` of a (20, N) float32 array; reload time of 49k / 200k / 1M under Rosetta.
- cv2 in TD's Python for png/jpg/exr depth files; `TOP.width` read in `pc_rt._aspect` is metadata only (no T-74).
- zkit on these pages (menus, RGB Tint, XYZ Target); Parameter Execute `pars` with `Offseta*` patterns.
- Instance count 0 never happens (an empty load keeps 1 zero sample); a failed load shows `ERROR: ...` in Status and
  keeps the previous cloud.

## Deviations from the spec (7.2) and why
- Added `kd` matching (default): offline it halves the travel distance against Morton for different shapes (banana
  -> torus 100k: 0.49 vs 0.87) at 0.2 s per 100k. `sliced` = sliced-OT flow + k-d instead of Morton refinement (Morton
  rank pairing of two different clouds is fragile: 2.1 vs 0.87 random in a probe).
- Shape `line` became `streak` (motion lines along the morph path); B2BK-style neighbour lines are FUTURE.
- `text` source (Text TOP -> cloud) is FUTURE: it needs a TOP readback or toptoPOP, both live-only (T-74/T-76).
- Live depth goes through the vertex shader (no `toptoPOP`, no readback); `toptoPOP` unprojection is a FUTURE A/B.
- Blend happens in the GLSL MAT vertex stage, not in a GLSL Advanced POP: one pass, zero CPU per frame.

## Not done / open
- Nothing live (all of the above). No `.tox` saved. No LEARNINGS entries (no TD facts yet).
- Lines between neighbours, text source, POP-native file loading (`pointfileinPOP`), sorted "over" blending,
  camera_bridge client inside the COMP (the depth TOP comes from outside for now).
