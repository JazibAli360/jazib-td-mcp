# pop_lane_h - lane H (POP-structural tail) offline prep: routes, builders, first frames, LIVE CHECKS, risk (27 Oct 2026, TD 2025.31550 target)

Lane H of `BUILD_PLAN_27OCT.md` s5 (rows from `docs/research/FX7b_td_creators_2025.md`). **Offline only:** no TD was
touched; every builder, numpy mirror and shader below is checked by offline tests (glslc against TD stubs, fake-TD build,
numpy). A live lane runs the items later, **one item per window, alone** (b3 / b4 / b5 saved and stopped, main quiet,
scratch only; T-124 GPU faults kill the other TDs, T-193 / T-194 GPU stalls hang them). Nothing here is measured: every
ms is an estimate; replace with `td_perf` + real fps.

## 0. The one decision that shapes the lane

The plan lists these items as "POP-structural" (Trail / Skin / Ray / Sprinkle / GLSL Advanced / Feedback POP chains,
attribute layouts). Read offline against the 31550 dump, the forum file and LEARNINGS, the lowest-risk construction for
**every** item avoids POP compute altogether:

- **Ray POP, GLSL ray queries, hardware collision and Sprinkle POP volume modes do not work on macOS** (MoltenVK has no
  ray queries; `Z_forum_nodes_comps.md` items 2 / 127 / 171, T-35, `BO_particle_sims.md`). TC-14 / TC-15 / TC-30 as
  written cannot be built here: analytic routes are built, the Ray / Sprinkle routes are FUTURE rows.
- **Trace POP** is not in 31550 (already in FUTURE). Skin POP sharp-curve artefacts are fixed only in 2025.33070.
  Feedback POP with a Null target crashed macOS in 32260 (fixed 32280; 31550 unverified). Neighbor-in-GLSL-POP has no
  confirmed build floor.
- What is proven on 31550: a **static Grid POP** (pars set once) -> Select POP -> **GLSL MAT** reading `TDPos()`
  (T-112), additive 1-px deposits into a 32F Render TOP (physarum, exact sums), **compute GLSL TOPs** (T-47), in-place
  state buffers (FX6 probe 5a), `shared` arrays + `barrier()` up to local_size 1024 (FX6 1a-1c).

So every lane-H COMP is: one or more static Grid POPs (or Sphere / Torus / Box POP generators) whose pars never change
live, a GLSL MAT that does the geometry maths in the vertex shader, and state in compute TOPs. No POP compute, no
attribute layouts, no Sort / TOP-to-POP configs (the T-124 trigger). The literal native POP chains survive only as
**gated optional probes** (TC-08 route B, TC-18 / TC-09 `Lines`), each run last in its window with abort rules.
Consequence: the risk of most items drops to the "new shader class" level; the coordinator may keep the H window
protocol anyway for first frames (recommended) or run the low-risk ones as ordinary scratch lanes.

## 1. Files (all new; owner = lane H)

| Item | COMP (in `/project1/lab`) | Builder | numpy mirror | Test |
|---|---|---|---|---|
| shared kit | - | `builders/pop_common.py` (op helpers, compute pass, static Grid POP + GLSL MAT + render, `_apply_first`) | - | `test/pop_testkit.py` (fake TD, glslc stubs for compute / MAT vertex / pixel) |
| TC-07 | POP_meshwarp | `builders/pop_meshwarp.py` | `pop_meshwarp_logic.py` (also the shared numpy hash / value noise) | `test/test_pop_meshwarp.py` |
| TC-19 | POP_terrain | `pop_terrain.py` | `pop_terrain_logic.py` | `test_pop_terrain.py` |
| TC-12 | POP_crack3d | `pop_crack3d.py` | `pop_crack3d_logic.py` | `test_pop_crack3d.py` |
| TC-30 | POP_caustics | `pop_caustics.py` | `pop_caustics_logic.py` | `test_pop_caustics.py` |
| TC-18 | POP_tree | `pop_tree.py` | `pop_tree_logic.py` | `test_pop_tree.py` |
| TC-11 | POP_rd3d | `pop_rd3d.py` | `pop_rd3d_logic.py` | `test_pop_rd3d.py` |
| TC-14 | POP_collide | `pop_collide.py` | `pop_collide_logic.py` (also the particle points MAT + look shared with TC-15) | `test_pop_collide.py` |
| TC-15 | POP_fillbody | `pop_fillbody.py` | `pop_fillbody_logic.py` | `test_pop_fillbody.py` |
| TC-08 | POP_tubes | `pop_tubes.py` | `pop_tubes_logic.py` | `test_pop_tubes.py` |
| TC-09 | POP_linegrowth | `pop_linegrowth.py` | `pop_linegrowth_logic.py` | `test_pop_linegrowth.py` |
| TC-10 | POP_branching | `pop_branching.py` | `pop_branching_logic.py` | `test_pop_branching.py` |
| TC-09 + TC-10 | - | `builders/pop_scan.py` (single-workgroup exclusive prefix scan GLSL + numpy mirrors; 2 users) | - | via both tests |

Offline: `python3 -I -m unittest discover -s test -p 'test_pop_*.py'` -> **140 tests OK** (27 Oct). Standalone COMPs on
purpose: the plan's homes (GEN_points, BO_particles, FX_glitch, FX_destroy, reaction_diffusion) belong to other lanes;
folding a module in later is a copy of its shader text, not a rewrite.

## 2. Order (safest first) and ratings

| # | Item | Risk | Why here |
|---|---|---|---|
| 1 | TC-07 meshwarp | low | static quads grid + MAT vertex warp; pilot of the kit |
| 2 | TC-19 terrain | low | same class, fbm in the vertex shader |
| 3 | TC-12 crack3d | low | pixel-shader Worley on built-in generator meshes |
| 4 | TC-30 caustics | low | grid points + analytic refraction + additive deposit (physarum class) |
| 5 | TC-18 tree (dust) | low | one compute pass, no inter-thread dependency |
| 6 | TC-11 rd3d | low | 4 compute GS steps + vertex texture fetch (new piece) |
| 7 | TC-14 collide | low | in-place compute particles (FX6 5a), Render Select of a compute buffer |
| 8 | TC-15 fillbody | low-medium | as 7 + texturebuffer array from a CHOP, heavier loops |
| 9 | TC-08 tubes (route A) | low | Feedback-TOP history + tall static grid with hidden seam quads |
| 10 | TC-09 linegrowth | medium | new class: one workgroup scan + scattered writes, manual dispatch 1x1x1 |
| 11 | TC-10 branching | medium-high | two scans back to back, allocation; only after TC-09 passed in an earlier window ("last, or never") |
| gated | TC-18 `Lines`, TC-09 `Lines`, TC-08 route B (native Particle -> Trail -> Skin POP) | medium | the only native POP-structure steps; each last in its own window, abort on any device error |

## 3. Window protocol (every item)

1. Coordinator: b3 / b4 / b5 saved and stopped, main quiet (no builds, no bring-homes), side watchdog on. Lane runs on
   **scratch** only. `python3 tools/lane.py add /project1/lab/<COMP> "lane H"`.
2. Step 1 = `build('/project1/lab', first=True)`: `first=True` applies the item's `FIRST` dict (small counts / low res)
   right after the pars and **before any render op exists** (`pop_common._apply_first`), so the first cook is the small
   one. Reply `notes` must be `[]` (every par set through `_try` reports misses there).
3. `td_watch` on the first cook; `td_errors` in a separate exec >= 2 frames later; `td_checkpoint` after each verified
   step.
4. Set and read in separate execs >= 2 frames apart; never `# allow-readback` (T-182). Readbacks = one read-only exec
   that saves `.npy`; references run in the lane's own Python from the `*_logic.py` mirror (T-184), never inside TD.
5. Raise counts / res one exec at a time after clean frames only (T-193); caps are hard (`clampmax`) on every count par.
6. **Abort, any item:** a "Vulkan Device Error" dialog, any side TD dying / hanging in the same 30 s, an exec timeout, a
   first cook stalling > 1 s, NaN in a state dump, or a parity check off by > 10x its tolerance. Then: stop the window,
   save nothing, LEARNINGS T-nn at once (T-135 numbering rule), crash pattern if code-shaped, item back to FIRST or
   parked. No live trial-and-error: a failed check is reported, not tuned.
7. End: verified -> by builder in main in a quiet minute (each COMP is < 60 ops, built in one exec), park, save, library
   export, "Verified live" here with cook ms + real fps, `lane.py remove`.

`<R>` below = `~/Documents/StageLab_PrismFest/jazib-td-mcp`. Every build line is
`ns = dict(globals()); exec(open('<R>/builders/pop_<item>.py').read(), ns); r = ns['build']('/project1/lab', first=True); r`.

## 4. Items (in run order)

### TC-07 POP mesh warp (Tex) -> `POP_meshwarp` (builders/pop_meshwarp.py, pop_meshwarp_logic.py, test/test_pop_meshwarp.py)

**Route (why lowest risk).** The plan's first check is answered offline: `gridPOP` on 31550 has `texture` (none / point /
vert, default point), so a Grid POP carries `Tex` (dump `ops_POP_2025.31550.json`). Rather than bending `Tex` with a POP
filter chain (Noise / Math Mix / Field POP on `Tex`: new attribute scopes, unprobed pars), the same maths runs in the
GLSL MAT vertex shader over ONE static Grid POP (quads, Cols x Rows, size 1 x 1, pars set once at build). The vertex
shader computes the warped texture coordinate uv', the depth dz and a finite-difference normal; the pixel shader samples
in1 at uv'. Grid POP + Select POP + GLSL MAT is the lab's proven class (physarum, GEN_points; T-112); the only new thing
is quads instead of points. Modes: ripple, swirl, slice, melt, wave, bulge, noise; Tilt / Orbit / Roll rotate the sheet
(geo transform) for real 3D depth. uv is taken from `TDPos().xy + 0.5` (not from `uv[0]`), so nothing depends on how
the MAT exposes `Tex`.

**Ops on 31550.** gridPOP (`surftype quads`, `cols`, `rows`, `sizex/y`, `texture point`), selectPOP (`pop`),
glslMAT (`vdat`, `pdat`, sampler / vec blocks, `blending`, `srcblend`, `destblend`, `depthtest`, `depthwriting`,
`cullface`, `wireframe`), geometryCOMP (`material`, rx/ry/rz), cameraCOMP (`viewanglemethod vertfov`, `fov`, `tz`,
`near`, `far`), renderTOP, constantCHOP + speedCHOP clock, switchTOP, in/out TOP. All in the dumps. Unverified live:
quads Grid POP through a GLSL MAT (points only so far), `TDWorldToProj(TDDeform(vec3))` on POP geometry, MAT
`wireframe tesselated` on macOS.

**Build steps** (one step per exec; `<R>` = `~/Documents/StageLab_PrismFest/jazib-td-mcp`):

1. `ns = dict(globals()); exec(open('<R>/builders/pop_meshwarp.py').read(), ns); r = ns['build']('/project1/lab', first=True); r`
   -> reply `notes == []`, ~13 ops. `first=True` applies the first-frame values below before any render op exists.
2. (>= 2 frames later) `td_errors /project1/lab/POP_meshwarp` -> 0; `op('/project1/lab/POP_meshwarp/mat').warnings()` empty.
3. Wire a test clip to in1 (Movie File In of `media/webcam/webcam_ref_5s.mp4` or a Ramp TOP), Amount 1. `td_checkpoint`.
4. LIVE CHECKS 1-7 below, then raise Cols/Rows to 128 x 228 (defaults) and 256 x 456; checkpoint after each.

**First-frame safe settings.** Cols 64, Rows 114 (7 296 points), Mode ripple, Strength 0.5, Depth 0.3, Speed 0.25, Shade
0.5, aa4, out 1080x1920 rgba16f. Hard caps on the pars: Cols <= 512, Rows <= 912 (467 k points).

**LIVE CHECKS**

| # | Check | Expected | How |
|---|---|---|---|
| 1 | build + compile | reply notes []; 0 errors / warnings on mat, render | td_errors, `.warnings()` |
| 2 | grid size | `op('sheet').numPoints` = Cols x Rows (7 296 at first frame, 29 184 at 128 x 228) | read in its own exec |
| 3 | Amount 0 | out1 == in1 exactly (diff 0) | dump both to .npy (read-only exec >= 2 frames after the change), compare outside TD |
| 4 | Strength 0 (each mode) | mean abs(out1 - in1) <= 1/255 | same dump; only the resampling of a full-frame sheet |
| 5 | flat parity, every mode | Depth 0, Shade 0, Tilt/Orbit/Roll 0, Zoom 1, Speed 0 (clock frozen; read `op('clock')[0]` = t): mean abs(out1 - `reference_mesh_flat(in1, p, 1080, 1920, Cols, Rows)`) <= 2/255, p99 <= 8/255 | `pop_meshwarp_logic.reference_mesh_flat` on the dumped in1 (outside TD, T-184) |
| 6 | depth on | ripple Depth 0.3: no NaN, alpha > 0 on >= 90 % of pixels at Zoom 1; Tilt 40: sheet visibly foreshortened (capture) | dump + one capture |
| 7 | cost | COMP <= 1.5 ms at 128 x 228 (Render TOP floor ~1 ms, T-198), real fps 60 with others parked; record 256 x 456 | td_perf + project fps |

**Cost estimate.** 1.0-1.6 ms (Render TOP CPU floor + a few hundred k vertex invocations); 256 x 456 ~ +0.2 ms.

**Risk: low.** Abort: any "Vulkan Device Error" dialog or TD error alert (stop, save nothing, LEARNINGS + crash
pattern); mat compile error not fixed by one text edit; parity 5 off by > 10/255 mean (wrong uv convention: check
`TDPos()` range first, do not iterate live); cost > 3 ms at 128 x 228.

### TC-19 Terrain flyover with LOD -> `POP_terrain`

**Route.** One static Grid POP (quads, Cols x Rows, size 2 x 2) drawn by a GLSL MAT; the vertex shader does all of it.
LOD = radial remap of grid coords g in [-1,1]^2 to world xz = sign(g)|g|^Lodpow x Extent (the clipmap's "dense near,
coarse far" with no rings or stitching). Fly-over = the noise domain scrolls by module time x Speed; Snap snaps the
scroll to the finest cell Extent x (2/(Rows-1))^Lodpow and shifts the vertex by the remainder (no swimming near the
camera). Height = Heightscale x fbm value noise (`#define MAXOCT 8`), Ridge, Seed. Styles are pixel-shader only
(shaded / contour / wire / ramp / data); normal from screen derivatives. Replaces the glsladvancedPOP clipmap
(Artcraft GridPOPLOD): no POP compute, no count change.

**Ops on 31550.** gridPOP, selectPOP, glslMAT, cameraCOMP (`vertfov`, fov, near, far, rx, ty, tz), renderTOP. Unverified:
quads Grid POP through a GLSL MAT, `dFdx` / `fwidth` on MoltenVK.

**Build steps.** (1) build first=True, `td_errors`. (2) read-only: `[c.op('mat').errors(), c.op('render').errors()]`.
(3) Style data, Speed 0 (set exec); >= 2 frames later dump `c.op('render').numpyArray(delayed=True)` (read twice, T-91);
`pop_terrain_logic.check_data(arr, params(...))` outside TD. (4) style sweep shaded / contour / wire / ramp, one
capture each; then defaults Cols = Rows = 160, Octaves 5, 1080x1920. (5) rebuild with panel, layout check, td_perf,
park, save.

**First frame.** `FIRST = Cols 96, Rows 96 (9 216 points), Octaves 3, Res 540x960`. Caps: Cols / Rows <= 512, Octaves <= 8.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | mat / render errors '' ; notes [] | read-only exec |
| 2 | Amount 0 | out1 == in1 (diff 0) | dump |
| 3 | data parity | covered pixels, r vs fbm(g, b): median <= 0.01, p99 <= 0.05 (offline cell error at defaults: median 0.0022, p99 0.014; ridge 0.0047 / 0.038) | Style data, Speed 0, rgba32f aa1 dump, `check_data` |
| 4 | LOD extents | data g / b inside [-Extent, Extent] | `check_data` bounds |
| 5 | no swimming | Snap on, Speed 1: two data dumps 1 s apart, same r at the same (g, b) within 2e-3 | `check_data` on both |
| 6 | grid | `numPoints` = Cols x Rows (9 216 / 25 600) | POP info (never iterate points, T-131) |
| 7 | cost | <= 3 ms, 60 fps, others parked | td_perf |

**Cost.** 1.0-1.8 ms at 160 x 160 (Render TOP floor ~1 ms, T-198); 512 x 512, 8 octaves +0.5-1 ms GPU.
**Risk: low.** Abort: device error; mat compile error unlike glslc's; stall > 0.5 s after step 1; data parity median >
0.05 (TDPos range assumption wrong: check that size 2 gives TDPos().xy in [-1, 1]; do not iterate).

### TC-12 Voronoi crack lines on a mesh -> `POP_crack3d`

**Route.** Cracks per pixel in a GLSL MAT: 3D Worley F1 / F2 of the object-space position (`TDPos()`, jittered cell
grid, 27-cell search, literal bounds); crack where F2 - F1 < Width (fwidth AA); front |p - Impact| <= Reach x Progress
with Soft edge, Auto loops; Erode discards whole cells (hash < Erode) the front has reached; styles lit (flat or in1 on
spherical uv), lines (premultiplied overlay), pos / data (checks). Meshes: Sphere (geodesic), Torus 96x48, Box 1.6,
each created once with fixed pars, picked by an expression on geo's Select POP `pop` (Shape) or a Custompop path.
Replaces Heckaman's glsladvancedPOP pre-allocated segments. Normals from dFdx / dFdy taken before any discard.

**Ops on 31550.** spherePOP (type geodesic, freq, rad), torusPOP, boxPOP, selectPOP, glslMAT, cameraCOMP, renderTOP.
Unverified: TDPos() on generator POPs, an expression-driven Select POP `pop`, discard + fwidth on MoltenVK.

**Build steps.** (1) build first=True, td_errors. (2) read-only: errors + sphere point count. (3) Style pos, Spin 0,
Auto off, Progress 1, Erode 0 -> dump; then Style data -> dump; `check_data(pos, data, params)` outside TD. (4) Erode 0.5
-> dump; compare alpha 0 pixels with `eroded(pos, params(erode=0.5))`. (5) Shape torus / box / custom, styles lit /
lines, one capture each. (6) panel build, perf, park, save.

**First frame.** `FIRST = Detail 8 (~1.3 k triangles), Res 540x960, Spin 0, Auto off`. Detail <= 96.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | errors '' ; notes [] | read-only |
| 2 | Amount 0 | out1 == in1 | dump |
| 3 | Worley parity | covered px with gap > 0.01: F1 p99 err <= 2e-3, gap p99 <= 2e-3; crack flag agreement >= 0.98 | pos + data dumps, `check_data` |
| 4 | crack coverage | ~0.18 of covered sphere px at defaults (numpy 40 k sphere points 0.180; Progress 0.5: 0.070; Width 0.1: 0.335), +-0.03 | data dump |
| 5 | erosion | Erode 0.5, Progress 1: removed mask = numpy `eroded()` (mismatch < 0.5 % of covered px); area ~0.51 (Progress 0.5 ~0.21) | pos dumps |
| 6 | shape switch | torus / box: errors '' and coverage > 0 | read after each set |
| 7 | cost | <= 3 ms, 60 fps | td_perf |

**Cost.** 1.2-2 ms (27-cell loop 0.2-0.6 ms GPU at full coverage). **Risk: low.** Abort: device error; compile error;
stall > 0.5 s at full res; check 3 > 10x tolerance (object space is not TDPos(): one probe `TDPos()` vs `P` on a scratch
copy, then stop). If the expression-driven Select POP faults: constant `pop` set at build only.

### TC-30 Caustics thrown by geometry -> `POP_caustics`

**Route.** Ray POP is not available on macOS -> FUTURE. Analytic refraction in the GLSL MAT vertex shader over one
static Grid POP of points (Rays x Rays), one parallel ray each (Lightangle tilts it). Refractor: water (4 travelling
sines, exact gradient normal), sphere (in + out refraction, TIR dropped; Direct = misses still light the floor), slab
(top = Thickness x in1 luma, the supplied logo as glass). `refract()` with eta 1/Ior in, Ior out; the floor hit at
-Floordepth is written straight to clip space over the Floorsize square (no camera maths); 1-px points additive one/one
into a 32F Render TOP `deposit` at Simres (0 = Rays: flat refractor = exactly 1.0 per texel), the physarum class. One
compute `look`: Persist accumulation in buffer 1 in place, tone 1 - exp(-Exposure x acc) x tint, optional add over
in1, premultiplied, cropped to the output aspect.

**Ops on 31550.** gridPOP points, selectPOP, glslMAT (one/one, depth off), renderTOP rgba32float aa1, glslTOP compute (2
bufs, readwrite, no clear), clock CHOPs, cameraCOMP (required, unused). Unverified: `textureLod` in a MAT vertex shader
(slab only).

**Build steps.** (1) build first=True, td_errors, checkpoint. (2) read-only errors / warnings. (3) checks 2-8: set in one
exec, >= 2 frames later save `op('deposit').numpyArray()` in a read-only exec, compare with
`pop_caustics_logic.deposit(params(...))`. (4) Rays 256 -> 512 -> 1024, one exec each, td_perf each. (5) park, save.

**First frame.** `FIRST = Rays 128 (16 384 rays), Simres 0, Persist 0, Size 1, Refractor water`. Rays <= 1024 (1 M).

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | no errors on mat / look; notes [] | read-only |
| 2 | flat water (Amp 0, Lightangle 0, Simres 0, Rays 128) | sum = 16 384 exactly, every texel = 1.0 | dump sum / min / max |
| 3 | sphere Ior 1.5, Radius 0.5, Floordepth 0.75 (= nR/(2(n-1))), Floorsize 2, Direct on | sum = 16 260 at 128 (65 104 at 256); peak within 1.5 texels of centre; peak ~184 at 128 (~475 at 256) +-10 % | dump vs `deposit()` |
| 3b | same, Direct off | sum = 3 104 at 128 (12 460 at 256) | dump |
| 4 | water keeps every ray (Amp 0.02, Freq 6, Floorsize 4) | sum = 16 384; max ~21; L1 vs numpy <= 2 % of N | Speed 0, mirror at `clock[0]` |
| 5 | slab, flat in1 | every texel = 1.0 | dump |
| 6 | look: Persist 0.5 >= 60 frames, Exposure 1, flat water | out1 rgb = (1 - e^-2) x tint within 1/255 | dump out1 |
| 7 | Amount 0 | out1 == in1 | dump |
| 8 | cost | Rays 256 <= ~1.5 ms; real fps | td_perf |

**Cost.** 1.0-1.6 ms at Rays 256; ~4-6 ms at 1 M (physarum numbers). **Risk: low.** Abort: device error / stall > 1 s;
a non-integer deposit sum or NaN; check 2 fails (mapping wrong: report, do not tune).

### TC-18 GPU branching tree (L-system on the GPU) -> `POP_tree`

**Route.** Implicit complete tree, B branches per node, breadth-first: node k > 0 has parent (k-1)/B, slot (k-1)%B;
N = (B^(Depth+1) - 1)/(B - 1) (Depth 10, B 2 = 2 047). ONE compute TOP `segs` (rgba32f, 2*side x side: texel 2x = start
xyz + level, 2x+1 = end xyz + width) where each thread walks its ancestor chain (`#define MAXD 20`) and composes from
the root: ry(slot x 2pi/B + level x Twist + jitter), rz(sway), rx(Spread + jitter); sway = Sway sin(t + 0.7 level) x
level/Depth; length x Ratio(1 +- Lenjitter) per level; Progress grows outward by level; lowbias32 hashes mirrored
bit-exact. Draw default = points dust along each segment (Samples, static Grid POP points, the GEN_points class).
`Lines` (off, gated) = a second static Grid POP lines 2 rows x N cols (liney only), Render TOP geometry by expression.
A `dims` CHOP clamps Depth per B (17 / 10 / 8 for B 2 / 3 / 4: <= 262 144 segments) and Samples (<= 1 M points).
The CPU turtle L-system stays in GEN_points `lsystem`.

**Ops on 31550.** gridPOP (points; lines with linex / liney), selectPOP, geometryCOMP, glslMAT, cameraCOMP, renderTOP
(geometry by expression), glslTOP compute (no inputs), constantCHOP, speedCHOP. Unverified (gate Lines only): a lines
Grid POP with liney only = separate 2-point segments; a 262 k-column Grid POP; the Render TOP `geometry` expression.

**Build steps.** (1) build first=True, td_errors. (2) Speed 0, Spin 0; >= 2 frames later save `op('segs').numpyArray()`
+ `op('clock')[0]`; compare with `pop_tree_logic.texture(params(time=clock*Swayspeed, ...))`. (3) Depth 14, then 17,
td_perf + dump each. (4) Lines on (gated, last). (5) park, save.

**First frame.** `FIRST = Branches 2, Depth 10, Samples 4, Lines off` (2 047 segments, 92x46 texture, 8 188 points).

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | no errors on segs / mat / lmat / look; notes [] | read-only |
| 2 | dims | b 2, deff 10, nseg 2047, side 46, samples 4, npts 8188, pside 91 | read the CHOP |
| 3 | segment parity (Speed 0) | start / end max err <= 1e-4; level exact; unused start texels w = -1 | dump vs `texture()` |
| 4 | caps | B 3, Depth 30 -> nseg 88 573; B 2, Depth 17, Samples 64 -> npts <= 1 048 576 (Samples clamped to 4) | dims CHOP |
| 5 | Progress 0.5, Depth 5 | level >= 3: start == end; levels 0-2 length > 0 | dump |
| 6 | Amount 0 | out1 == in1 | dump |
| 7 | Lines gate (after 1-6) | 2 x nseg points, same tree in a capture, no errors | POP info + capture |
| 8 | cost | Depth 10 <= ~1.5 ms; record Depth 17 (aim <= 3 ms) | td_perf |

**Cost.** segs 0.1-0.4 ms at 262 k; render floor 1-1.3 ms. **Risk: low** (dust), **medium** (Lines). Abort: device error
/ stall > 1 s; parity worse than 1e-3 (report); with Lines: any error or cook > 5 ms -> Lines stays off, LEARNINGS.

### TC-11 3D reaction-diffusion structures (POP <-> TOP) -> `POP_rd3d`

**Route.** TOP side: Gray-Scott on a wrap texture (Simres^2 rgba32f; r U, g V, b step count) as a fixed chain of 4
compute TOPs `gs1..gs4` (one step each, same text, Karl Sims 3x3 Laplacian, Du 1, Dv 0.5, dt 1); `step_sel` (Steps 1 /
2 / 4) -> Null `state` -> Feedback `state_fb` -> gs1. `Stopat` freezes after exactly N steps whatever the frame rate
(exact parity without timing tricks). Presets coral / mitosis / worms / spots / maze / custom; Reseed = hash spot seed.
POP side: one static Grid POP `surf` (quads); the MAT vertex shader maps (u, v) to torus (both wrap = texture wrap) /
sphere / plane, pushes along the normal by Height x V (`textureLod` in the vertex shader), finite-difference normals;
palette by V, lambert + rim; Spin / Tilt on geo.

**Ops on 31550.** glslTOP compute, feedbackTOP, switchTOP, nullTOP, constantTOP, gridPOP, selectPOP, glslMAT
(sampler extend repeat, cullface, depth), geometryCOMP, cameraCOMP, renderTOP, parameterexecuteDAT, clock CHOPs.
Unverified: `textureLod` in a MAT vertex shader (new to the lab); sampler extend repeat (the shader also uses fract()).

**Build steps.** (1) build first=True, td_errors. (2) read-only error scan, checkpoint. (3) Stopat 50, Seed 1, coral,
Steps 1, pulse Reseed. (4) ~1 s later read-only: dump `op('state')`; compare with
`pop_rd3d_logic.run(128, 128, 1, 0.0545, 0.062, 50)`. (5) defaults Simres 256, Cols 256, Rows 128, Steps 4, Stopat -1;
td_perf, checkpoint, save, park.

**First frame.** `FIRST = Simres 128, Cols 128, Rows 64, Steps 1`. Caps Simres <= 1024, Cols / Rows <= 512.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | 0 errors on gs1..gs4, mat, render; notes [] | td_errors |
| 2 | seed | Reseed + Stopat 0: V in {0, 1}, V mean = numpy `seed_state(128, 128, 1)` exactly; U = 1; b = 0 | dump |
| 3 | GS parity | Stopat 50, coral, seed 1: max abs(U - U_np), abs(V - V_np) <= 1e-3; b = 50 everywhere | dump vs numpy float32 |
| 4 | Stopat freeze | two dumps 1 s apart: diff 0 | two read-only execs |
| 5 | Play off | diff 0 across 1 s | two dumps |
| 6 | Steps 4 | b +4 per cooked frame | dump twice + cook count |
| 7 | surface | Height 0 torus: radius 0.6 +- 0.25 = `pop_rd3d_logic.base('torus', u, v)` | capture + logic |
| 8 | Amount 0 | out1 == in1 | dump |
| 9 | cost | gs <= 0.1 ms each at 256^2; COMP <= 3 ms; 60 fps | td_perf |

**Cost.** 1.2-2 ms. **Risk: low.** Abort: device error; a neighbour TD stops replying; a gs pass > 2 ms at 128^2; NaN.
Fallback if the vertex texture fetch fails: Height 0, colour only (V sampled in the pixel shader).

### TC-14 Particle collisions -> `POP_collide`

**Route.** Ray POP / hardware collision are not on macOS -> FUTURE. Analytic SDF colliders in ONE compute TOP `state`
(side x side, 2 rgba32f buffers in place, FX6 5a: b0 = pos + life, b1 = vel + generation; Testmode b1.w = steps since
reset). Colliders in fixed order: floor, 4 spheres, 2 axis-aligned boxes; push out along the analytic normal, normal
velocity x Restitution, tangential x (1 - Friction). Emitter point / disc / line, gravity, value-noise wind, drag,
`#define SUBSTEPS 4`, fixed dt = Speed/60 per cook (deterministic), respawn at life end, NaN guard. Draw: static Grid
POP points + points MAT (TDPos() -> texel, hue by speed, additive) via Camera + TDWorldToProj; compute `look` (Persist)
over in1. The shared particle MAT / look text lives in `pop_collide_logic.py` (used by TC-15 too).

**Ops on 31550.** gridPOP, glslTOP compute (numcolorbufs, readwrite, clearoutputs), renderselectTOP (`bufferindex`, the
shatter pattern), glslMAT, cameraCOMP, renderTOP, parameterexecuteDAT, clock CHOPs. Unverified: a MAT sampling a Render
Select of a compute buffer; `fetch('jz_reset')` in a uniform expression (person_mask uses it).

**Build steps.** (1) build first=True, td_errors, layout check, checkpoint. (2) Testmode on, sphere / box colliders off,
Friction 0, Substeps 4; >= 2 frames later dump texel (0,0) of `state` b0 and `state_v`; compare with
`pop_collide_logic.test_series(...)` at k = state_v.w. (3) Testmode off, defaults, Count 4096; ~5 s later dump b0;
checks 3-5. (4) Count 16 384, Substeps 2, Persist 0.8; td_perf + fps; capture; save.

**First frame.** `FIRST = Count 4096, Substeps 1, Size 2, Persist 0`. Count <= 262 144, Substeps <= 4.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | 0 errors on state / look / mat; notes [] | td_errors |
| 2 | Testmode series | y_k = `test_series` row k within 1e-3 (bounces may shift one step near contact) | dump texel 0, k = b1.w |
| 2b | bounce apex (Testh 0.4, Floory -0.45, h 0.85, e 0.5, Substeps 4) | apexes above the floor 0.2115 / 0.0519 / 0.0128 (e^2 h = 0.2125); Substeps 1: y -0.2446 / -0.3998 / -0.4386 | numpy series vs samples |
| 3 | floor | min y >= Floory - 1e-4 (numpy 300 frames: exactly -0.45) | dump b0 |
| 4 | spheres / boxes | no live particle inside an enabled collider (tolerance 1e-4) | dump b0, numpy |
| 5 | alive / finite | alive ~ Count (numpy 300 frames: 4 090 / 4 096); no NaN / Inf | dump |
| 6 | Amount 0 | out1 == in1 | dump |
| 7 | cost | <= 3 ms; real fps | td_perf |

**Cost.** 1.5-2 ms (state < 0.2 ms at 16 k). **Risk: low.** Abort: device error; one exec timeout; NaN; fps < 50 at
<= 16 k. Then Count -> FIRST, Amount 0, park, LEARNINGS.

### TC-15 Swarm fills an animated body -> `POP_fillbody`

**Route.** Sprinkle POP volume / Ray POP inside tests need hardware ray tracing -> FUTURE. Body = SDF union of <= 16
capsules; `caps` (compute 16x2 rgba32f) writes the table each frame from an in-shader procedural dancer (12 capsules;
body time = clock x Dancespeed + Posetime; Pose; origin / scale) or from CHOP rows (in CHOP x y z w, sample 2k = a + r,
2k+1 = b; Switch CHOP keeps a 1-sample stand-in so the texturebuffer array is never empty; index guarded, T-35).
`state` = one compute TOP, 2 buffers in place: spawn inside by bounded rejection sampling (`TRIES 32`, fallback capsule
point a); step = value-noise wander + damping; if sdf > -Margin project along the central-difference gradient and drop
the outward velocity (so the swarm follows the moving body); hashed respawn fraction. Same points MAT / look as TC-14.
**Perf wave 27 Oct (b2 -> main):** the `caps` pass is merged into `state`: the first 32 threads of each 8 x 8
workgroup build the 16 x 2 table (dancer or CHOP rows, `uB` / `uB2` / `uCaps` now on `state`) into `shared` arrays
before any return (per-thread arrays were the slow T-187 pattern). Twin parity on b2: old caps + state vs merged state
from the same Reset, 150 frames, 16 384 points: max diff 0.0. state + caps 0.7 -> 0.3 ms; step 2 above now dumps the
table only through `state` (no `caps` op).

**Ops on 31550.** as TC-14 + inCHOP / constantCHOP / switchCHOP / nullCHOP and a glslTOP texturebuffer array from a CHOP
(physarum `uRows`, proven). Unverified: switchCHOP `index` by expression.

**Build steps.** (1) build first=True, td_errors, layout, checkpoint. (2) Dancespeed 0, Posetime 1.25, Pose 1; dump
`caps` >= 2 frames later; compare with `pop_fillbody_logic.caps_table(params(tb=1.25))`. (3) Reset, wait 120+ frames,
dump b0 + clock; `inside_fraction` outside TD with caps from the same read. (4) Dancespeed 0.5: check 4; Count 16 384;
Persist 0.85; td_perf, capture, save.

**First frame.** `FIRST = Count 4096, Substeps 1, Size 2, Persist 0`. Count <= 262 144, Substeps <= 4.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | 0 errors on caps / state / look / mat; notes [] | td_errors |
| 2 | dancer joints (tb 1.25, Pose 1, origin (0, 0.04, 0), scale 0.9) | caps = `caps_table` within 1e-5; e.g. row 0 k0 = (0.045, -0.032, 0, 0.0675), k1 = (0.076284, 0.2875, 0, 0.0585), k2 = (-0.009216, 0.1885, 0, 0.0315); row 1 k0 b = (0.067284, 0.211, 0, 1); valid 1 for k < 12, 0 above | dump caps |
| 3 | inside after reset, frozen pose | fraction(sdf <= 0) >= 0.99 (numpy 1.000) | dump b0 + caps |
| 4 | inside while dancing (0.5, 120 frames) | >= 0.99 (numpy 1.000, max speed 0.44) | as 3 |
| 5 | finite / drawn | no NaN; b0.w in (0.5, 1] for i < Count, -1 beyond | dump |
| 6 | CHOP body (2 capsules from a Table) | caps rows = `caps_table(..., rows)` (1e-5), k >= 2 invalid | dump caps |
| 7 | Amount 0 / cost | out1 == in1; <= 3 ms | dump; td_perf |

**Cost.** 1.7-2.3 ms (state ~0.3-0.6 ms at 16 k x 2 substeps). **Risk: low-medium.** Abort: device error / timeout; state
GPU > 2 ms at 16 k (Substeps 1 or Count 8 k); inside < 0.95; NaN.

### TC-08 Light-trail tubes -> `POP_tubes`

The TC-08 *look* is already live through lane G (PX_lines on BO_particles); lane H's item is tube geometry.

**Route A (default).** History texture `hist` (Samples x Tracks rgba32f, xyz + time stamp, column 0 = head) shifted by
one compute pass through Feedback `hist_fb` (an in-place shift would race: thread k reads what k-1 writes; the Feedback
shift is order-free, the GEN_points `state_fb` class). Heads: lissajous / vortex (analytic), flow (smooth trig field,
dt from the stamp, clamped 0.1), input (in2 texel i, e.g. BO_particles state; lissajous when unwired). Reset / size
change fills every column with the head. Tube mesh = ONE static tall Grid POP (quads, Samples x Tracks x (Sides + 3)
rows): per track Sides + 1 ring rows + 2 seam rows placed so the bridging quads are zero-area or discarded in the pixel
shader (gap flag). Ring = central-difference tangent + Gram-Schmidt frame (same smooth-curve limit as Skin POP on
31550), radius x (1 - k/(K-1))^Taper, colour head -> tail with Fade, additive, halo from render mips in the look.
Instancing with `TDInstanceID()` was rejected: POP mesh instancing with a CHOP source is unverified on 31550 (only point
sprites, T-15); the waste of the tall grid is 2/(Sides+3) of the quads.

**Route B (optional, `build(..., native=True)`; gated).** Sub-COMP `native` (allowCooking off until the probe): Point
Generator POP (32) -> Particle POP (maxparticles 32, birthrate 16, life 2) -> Trail POP (30 frames, surftype rows) ->
Skin POP -> geo -> render 1080x1920 aa1; `Route native` shows it through out_sel input 2.

**Ops on 31550.** A: glslTOP compute (+ inputfiltertype mipmap), feedbackTOP, constantTOP, switchTOP, gridPOP,
selectPOP, glslMAT, geometryCOMP, cameraCOMP, renderTOP, parameterexecuteDAT, speedCHOP. B: dump par names only;
Trail / Skin behaviour, Skin output topology from Trail rows (ribbon vs tube) and Particle POP without targetpop are
unverified.

**Build steps.** (1) build first=True, td_errors. (2) read-only error scan, checkpoint. (3) lissajous, Play off, pulse
Reset; next exec Play on; ~1 s later Play off. (4) >= 2 frames later dump `op('hist')`; compare outside TD. (5) defaults
Tracks 64, Samples 64, Sides 8; td_perf, checkpoint, save. (6) Route B only at the end of a window, alone: build
native=True; next exec `native.allowCooking = True` under td_watch; >= 2 frames later read errors of `native/*` +
`op('native/skin').numPoints`; one capture; allowCooking False.

**First frame.** `FIRST = Tracks 16, Samples 32, Sides 6` (4.6 k mesh points). Caps Tracks <= 256, Samples <= 128,
Sides <= 16 (~620 k points). Route B: 32 particles x 30 samples.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | hist / look / mat / render 0 errors; notes [] | td_errors |
| 2 | reset fill | after Reset + Play off: every column = column 0 (diff 0) | dump hist |
| 3 | shift parity | lissajous: hist[:, k, :3] = `head('lissajous', i, w[i,k], Scale, Seed)` at each texel's stamp, <= 1e-5; w[k] - w[k+1] = one cook's clock step | dump |
| 4 | ring radius | `pop_tubes_logic.vertex` on the dumped hist gives Radius (1 - k/(K-1))^Taper; capture of 1 track (Radius 0.05, Speed 0): width = 2 Radius H / (2 Dist tan(fov/2)) +- 1 px | logic + capture |
| 5 | seams hidden | Tracks 2 far apart: 2 tubes, no bridge | capture |
| 6 | Amount 0 | out1 == in1 | dump |
| 7 | in2 source | column 0 = in2 texels x Scale (<= 1e-6) | dump both |
| 8 | cost | hist < 0.05 ms, render ~1-1.5 ms, look 0.2-0.4 ms, <= 3 ms | td_perf |
| B1 | native probe | no device error in 60 s; skin numPoints > 0 and small; 60 fps | td_watch + read-only |

**Cost.** A 1.5-2.2 ms; B tiny. **Risk: A low, B medium.** Abort A: device error, hung neighbour TD, NaN in hist. Abort
B: any Vulkan dialog, freeze > 5 s or a neighbour TD death -> `native.allowCooking = False`, LEARNINGS + crash pattern,
route B dropped for 31550.

### TC-09 Differential line growth -> `POP_linegrowth`

**Route.** No Neighbor POP, no GLSL POP. Nodes in a 128x65 rgba32f state (rows 0-63 up to 8 192 nodes xy; texel (0,64) =
count, frame). Per frame two compute TOPs: `forces` (one thread per node: seed on Reset / count 0; spring to both
neighbours + align, brute-force repulsion over shared tiles of 256 (2 KB), boundary circle, hashed jitter, step clamp)
and `insert` = ONE workgroup of 1024 threads x 8 nodes, autodispatch off, dispatch 1x1x1: flag edges > Maxedge,
exclusive scan (`pop_scan.py`, 4 KB shared), midpoint after each accepted split in order, budget = Maxnodes - count,
earliest flags win. Feedback `state_fb` <- insert. Draw: static 128x64 Grid POP points + MAT (TDPos()), additive 32F;
`look` over in1. `Lines` (off, gated): Grid POP 1 x 8 193 linestrips, `view_sel` cooks only the chosen render.

**Ops on 31550.** glslTOP compute (autodispatchsize, dispatchsize x/y/z), feedbackTOP, constantTOP, switchTOP,
parameterexecuteDAT, gridPOP (points / linestrips), selectPOP, glslMAT, geometryCOMP, cameraCOMP, renderTOP.
Unverified: a rows-1 linestrips Grid POP draws one strip in index order (Lines gate); manual dispatch 1x1x1 at this
size (FX6 1c proved manual dispatch at another size).

**Build steps.** (1) `lane.py add`. (2) build first=True, notes []. (3) >= 2 frames later td_errors. (4) checks 1-6. (5)
optional Lines 1, check 7. (6) save, park, `lane.py remove`.

**First frame.** `FIRST = Maxnodes 1024, Seedcount 64, Res 540x960, Lines off` (texture size fixed: nothing reallocates).

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | 0 errors on forces / insert / look / mat | td_errors |
| 2 | count after the first insert frame | **exactly 128** (64 seed edges of 0.0098 > Maxedge 0.009) | texel (0,64).x of the dump |
| 3 | seed | radius 0.1 within 1e-6 | dump vs `seed_nodes` |
| 4 | one forces step | within 1e-4 of `logic.forces(P, cnt, frame, p, np.float32)` | step one frame, dump |
| 5 | counts frames 1-8 | 128, 150, 250, 386, 516 ... +-2 % per frame; = Maxnodes once capped (~frame 10) | count texel per stepped frame vs `run()` |
| 6 | finite, cost | no NaN; <= 3 ms at 1024 nodes; record 4096 / 8192 | td_perf |
| 7 | Lines (optional) | nodes in order, no stray line to the origin, loop closes; POP info 8 193 points | capture |

**Cost.** forces 0.1-0.3 ms at 1 k, 1.5-3 ms at 8 k; insert 0.05-0.2 ms; total 1.3-1.8 ms at 1 k. **Risk: medium** (new
class: one-workgroup scan + scattered writes). Abort: device error or first-cook hang > 10 s (no retry in that window);
check 2 != 128 (do not raise Maxnodes); NaN; forces > 5 ms at 4 096 -> cap Maxnodes 2 048.

### TC-10 Emergent feedback branching -> `POP_branching` (last, or never)

**Route.** No Feedback POP add / delete. Tips in a 64x65 rgba32f state (x px, y px, heading, age; texel (0,64) = count,
frame); trail rgba32f at Simw x Simh. `tips` (one thread per tip: seed centre burst / bottom row; 3 sensors like
physarum, turn away from trail, wander, move; die on dense trail ahead / wall / Maxage; split flag with chance Splitrate
x (1 - density / Killthresh)); `alloc` = ONE workgroup, dispatch 1x1x1, two scans: survivors densely (heading +
Splitangle), then children (heading - Splitangle, age 0), capped at Maxtips; deposit = static 64x64 Grid POP points
additive into 32F (physarum class); `trail` = (trail + (3x3 mean - trail) x Diffuse) x Decay + deposit; `look` hue by
age over in1. Feedbacks `state_fb` <- alloc, `trail_fb` <- trail.

**Ops on 31550.** as TC-09. Unverified: two scans back to back in one workgroup (every barrier reached by all threads).

**Build steps.** `lane.py add`; build first=True (notes []); td_errors >= 2 frames later; checks 1-5; then Simw 540 /
Simh 960 / Maxtips 1024, then 4096, only after clean frames, checkpoint each; save, park, `lane.py remove`.

**First frame.** `FIRST = Maxtips 256, Seedcount 8, Simw 270, Simh 480, Res 540x960`. Maxtips <= 4096.

| # | Check | Expected | How |
|---|---|---|---|
| 1 | compile | 0 errors on tips / alloc / trail / look / dep_mat | td_errors |
| 2 | seed | count 8, tips at (Simw/2, Simh/2), headings 2 pi i / 8 | dump vs `seed_tips` |
| 3 | tip count at K = 1, 5, 10, 30, 60 | = `run(K, p, np.float32)` exactly (numpy counts 8, 9, 15, 16, 23, 28 at frames 0-50 step 10; f32 = f64 for 60 frames at 270x480); after 60 within +-10 % | count texel per stepped frame |
| 4 | trail sum | S_t = Decay S_{t-1} + Deposit N_t, rel err <= 1e-3 | trail dump summed outside TD |
| 5 | finite, cost | no NaN; <= 3 ms at 540x960, 1024 tips | td_perf |

**Cost.** 1.5-2 ms. **Risk: medium-high.** Run only after TC-09 passed all checks in an earlier window. Abort (strict):
device error, a hang, or a side TD dying in the same 30 s -> stop the window, LEARNINGS + crash pattern, item marked
"never" until the user decides; count wrong at K = 1; trail sum error > 1e-2. Count saturating at Maxtips with the look
flooding (< 1 % deaths / frame for 300 frames) is tuning, not a fault: lower Splitrate, record it.

## 5. FUTURE (rows added to docs/FUTURE.md)

Ray-POP collisions / caustics / surface trails (TC-14, TC-30), Sprinkle POP volume fill (TC-15), Skin POP sharp-curve fix
(TC-08, 2025.33070), native Feedback-POP branching (TC-10, 2025.32280+), Neighbor-in-GLSL-POP line growth (TC-09),
POP mesh instancing with `TDInstanceID()` (TC-08, probe), Alaghast L-System POP (TC-18, x86_64 plugin). Ideas that run on
31550 but are POP compute (T-124 class) stay ideas, not built: glsladvancedPOP clipmap rings (Artcraft GridPOPLOD,
licence unread) and Heckaman crack segments as real POP lines.

## 6. Open notes for the coordinator / pop_common owner

- Not done offline (needs TD): every "unverified" line above; they are LIVE CHECK 1 of each item.
- Kit follow-ups suggested by the item lanes (not applied, no live need yet): an RGB par style in `_pars` (terrain and
  crack3d carry a local `_rgb_pars`), a shared GLSL hash string (lowbias / h2 / vnoise is repeated in meshwarp,
  terrain, crack3d, collide), `_compute(dispatch=..., arrays=...)` (linegrowth / branching / fillbody set them by hand),
  a `_reset_pulse(c)` helper (4 builders repeat the parameterexecuteDAT `Resetat` pattern), `_out_switch(index_expr)`.
- STATUS.md and LEARNINGS.md were not touched (no live fact or bug in this offline lane).

## 7. Live results (lane H live, b5 alone, 27 Oct 2026, TD 2025.31550)

Method: build first=True on b5, one step per exec; set and read in separate execs; dumps = read-only exec saving .npy
to `output/checks/pop_lane_h/`, references run outside TD (T-184); cost = `builders/perf_pull.py` (pump 150-180
pulled frames, pane elsewhere, others parked; machine load average ~20-30, so absolute ms carry the T-198 load spread).

| # | Item | Result | Numbers | Cost (ms, median) | Main |
|---|---|---|---|---|---|
| 1 | TC-07 POP_meshwarp | **pass** (after one shader fix, T-204) | notes []; 0 errors; numPoints 7 296 / 29 184 / 116 736; Amount 0 diff 0.0; Strength 0 mean 5e-6; flat parity 7 modes mean <= 0.104/255, p99 <= 0.87/255 (tol 2 / 8); Depth 0.3: no NaN, alpha > 0 on 96.7 %; Tilt 40 foreshortened (capture `POP_meshwarp_tilt40.png`) | 1.7 at 64x114, **2.05 at 128x228**, 2.13 at 256x456 (render CPU 1.2-1.3, T-198 floor); pull fps 53-57 | built by builder, Generators stage, parked, JazibTD_home.776; library 0.1.0 |
| 2 | TC-19 POP_terrain | **pass** | notes []; 0 errors; numPoints 9 216 / 25 600; Amount 0 diff 0.0; data parity (96x96, 3 oct) median 6.9e-4, p99 8.1e-3 (tol 0.01 / 0.05), cover 0.68, no NaN; extents x +-15.6, z (minus scroll) within -Extent; swim (Snap, Speed 1, 1.35 s apart, same world point binned 0.002): near band p99 1.7e-3 (<= 2e-3), mid band p99 6.3e-3 (coarser rings shift by the remainder, as designed); 4 styles compile + render (`POP_terrain_styles.png`). Seen: shaded is faceted near the camera (screen-derivative normal), wire draws a bright centre column where Lodpow 2 packs lines (cosmetic) | **2.28 at 160x160, 5 oct, 1080x1920** (render CPU 1.45); pull fps 48 at load 29 | Generators, parked, JazibTD_home.780; library 0.1.0 |
| 3 | TC-12 POP_crack3d | **pass** (after a compile fix and a cost fix, T-205) | notes []; first build: pixel compile error on `F1` / `F2` (renamed wF1 / wF2); Amount 0 diff 0.0; Worley parity F1 / gap p99 7e-8 / 1e-7 (tol 2e-3), crack agreement 1.0; coverage 0.177 of covered px (new hash: numpy 40 k sphere points 0.189, Progress 0.5 0.071, Width 0.1 0.346); Erode 0.5 removed 0.516 = numpy, mismatch 0.0 (numpy whole sphere 0.568, Progress 0.5 0.247); torus / box / custom ('../torus' via Custompop) errors '' with coverage 0.47 / 0.69, expression-driven Select POP fine; captures `POP_crack3d_styles.png` | was 5.8 (render GPU 3.6); after one-hash-per-cell + squared distances **3.48 at Detail 24, 1080x1920 aa4** (render CPU 1.3 + GPU 1.64); 540x960: 3.26 before the fix | Generators, parked, JazibTD_home.784; library 0.1.0 |
| 4 | TC-30 POP_caustics | **pass** (after one look-shader edge fix, T-204 class) | notes []; Amount 0 diff 0.0; flat water sum 16 384, every texel 1.0; sphere (Ior 1.5, R 0.5, depth 0.75) sum 16 260 = numpy, peak 199 vs 184 (+8 %, tol 10 %) at the same texel; Direct off 3 104 = numpy; water (Amp 0.02, Freq 6, Floorsize 4) sum 16 384, max 41 = numpy, L1 0.74 % of N; slab flat in1: every texel 1.0 (slab over the noise source: sum 10 462 vs 10 460, L1 22 %: steep luma gradients, not a check); all deposits integer, no NaN; look Persist 0.5 / Exposure 1: rgb = (1 - e^-2) tint within 0.104/255 after clamping the deposit read to the edge texel centres (first run: top / bottom 7 rows off by 53/255) | Rays 256: **2.43**, 512: 2.59, 1024: 3.39 (deposit GPU 0.13 / 0.37 / 0.95); deposit CPU 1.3 = Render floor | Generators, parked, JazibTD_home.788; library 0.1.0 |
| 5 | TC-18 POP_tree | **pass** (dust + Lines gate) | notes []; 0 errors (segs / mat / lmat / look compiled); dims b 2, deff 10, nseg 2 047, side 46, samples 4, npts 8 188, pside 91 (exact); segment parity Depth 10 start / end max 1.1e-6, Depth 14 1.3e-6, level exact, unused w -1, no NaN; caps B 3 Depth 30 -> Depth 17 (clamp) -> deff 10, nseg 88 573; B 2 Depth 17 Samples 8 -> samples 4, npts 1 048 572; Progress 0.5 Depth 5: levels >= 3 length 0, levels 0-2 >= 0.147, parity 4e-7; Amount 0 diff 0.0; Lines on: lines_grid 4 094 points (= 2 x nseg), same tree, no stray line, 0 errors (`POP_tree_draw.png`) | Depth 10: **3.45** (render CPU 1.34, segs 0.39, look 0.37; pull fps 35-45 with 6 TDs at 60-110 % CPU); Depth 14: 3.92; **Depth 17: 5.84** (render GPU 2.0, segs GPU 0.9: over the 3 ms aim, record); Lines Depth 10: 3.49 | Generators, parked, JazibTD_home.790; library 0.1.0 |
| 6 | TC-11 POP_rd3d | **pass** | notes []; 0 errors on gs1..gs4 / mat / render; textureLod in the MAT vertex shader works; Reseed + Stopat 0: V in {0, 1}, V mean 0.097412 = numpy exactly (diff 0), U 1, b 0; GS parity Stopat 50 coral seed 1: max dU 4.2e-7, dV 4.5e-7 (tol 1e-3), b = 50 everywhere, no NaN; Stopat freeze diff 0.0; Play off diff 0.0; Steps 4: b +220 over 55 state cooks = 4.0 / cook; Amount 0 diff 0.0; captures `POP_rd3d_shapes.png`. Default Dist 2.6 -> **5.2** (the torus overflowed the 9:16 frame) | **3.74 at Simres 256, 256x128, Steps 4** (render CPU 1.76; gs GPU 0.03-0.09 each) | Sims + point clouds, parked, JazibTD_home.794; library 0.1.0 |
| 7 | TC-14 POP_collide | **pass** | notes []; 0 errors on state / look / mat; a MAT sampling a Render Select of a compute buffer works; Testmode series (Substeps 4, Friction 0, colliders off) at k = 28 ... 299: dy <= 5.4e-7 off contact, 5.1-7.9e-4 at k 196-249 near contact (tol 1e-3), resting y = -0.45 exact; numpy apexes 0.2115 / 0.0519 / 0.0128; free run 4 096 (~6 s): min y -0.450000, spheres / box min sdf >= -1.3e-8 (none inside), alive 4 086, no NaN / Inf; 16 384: alive 16 326, no NaN. Look is dim at the defaults (Bright 0.6, 2 px) over black: cosmetic | **4.26 at 16 384, Substeps 2, Persist 0.8** (render CPU 1.66 + GPU 0.69, state 0.54, look 0.47): over the 3 ms aim | Sims + point clouds, parked, JazibTD_home.798; library 0.1.0 |
| 8 | TC-15 POP_fillbody | **pass** (checks); look finding below | notes []; 0 errors on caps / state / look / mat; dancer joints (tb 1.25, Pose 1): caps = `caps_table` within 6.5e-8, row 0 k0 (0.045, -0.032, 0, 0.0675), row 1 k0 b (0.0673, 0.211, 0, 1), valid 1 for k < 12; inside after Reset (frozen) 1.000, while dancing 0.5 (~180 frames) 1.000, at 16 384 1.000; b0.w in (0.50, 1.0]; no NaN; CHOP body (Table -> DAT to CHOP `chanpercol`, 4 samples x y z w): caps rows within 5e-9, k >= 2 invalid, switchCHOP index expression fine; Amount 0 diff 0.0 | **4.23 at 16 384, Substeps 2, Persist 0.85** (render CPU 1.61 + GPU 0.54, state 0.47, look 0.42, caps 0.30): over the 3 ms aim | Sims + point clouds, parked, JazibTD_home.800; library 0.1.0 |
| 9 | TC-08 POP_tubes (route A) | **pass**; route B not run (gated: its own window, last) | notes []; first build: layout failed on the stage list naming route-B ops (`native`, `native_sel`) that only exist with native=True: builder now drops missing names; 0 errors on hist / look / mat / render; reset fill: every column = column 0, diff 0.0; lissajous shift parity max 5.7e-6 (tol 1e-5), stamps step one cook (1/60, 2/60 on a dropped frame); in2 source column 0 = in2 texel x Scale within 4.8e-8; Amount 0 diff 0.0; 2 tracks Radius 0.05: two tapered tubes, no bridge (`POP_tubes_2tracks.png`); defaults 64 x 64 x 8 (45 056 points), no NaN (`POP_tubes.png`) | **5.64 at 64 x 64 x 8, aa4** (render CPU 1.8 + GPU 1.7-1.9; aa2 GPU 1.22, total 5.06); hist 0.49, look 0.43: over the 3 ms aim | Generators, parked, JazibTD_home.804; library 0.1.0 |
| 10 | TC-09 POP_linegrowth | **pass** (incl. the optional Lines check) | notes []; 0 errors on forces / insert / look / mat / mat_lines; one-workgroup scan with manual dispatch 1x1x1 ran clean; seed radius 0.1 within 6e-9; stepping by Play toggles with Jitter 0: frames matched by count + position, 8 live frames from the seed = mirror (forces then insert: 128, 128, 128, 256, ..., 768) within 1.4e-7, cap 1024 reached exactly (mirror 5 more frames, 8.6e-8); Jitter 0.1, 7 forces steps (salt = frame texel) within 2.8e-7 (tol 1e-4); no NaN at 1 024 / 4 096 / 8 192; Lines: strip 8 193 points, closed loop in index order, no stray line (`POP_linegrowth_views.png`). Note: the live sequence after Reset with Play on is forces-then-insert, `run()` is insert-first (first count 128 either way). Note (**gated since 7b**): `render_lines` cooks whenever the pane is inside the COMP (its viewer pulls it, ~1.0-1.3 ms CPU); with the pane elsewhere only the chosen render cooks | **4.70 at 1 024, 1080x1920** (render CPU 1.8 + GPU 0.48, look 0.47, forces 0.39); 4 096: 5.13 (forces GPU 0.84); 8 192: 5.58 (forces GPU 1.38; < 5 ms forces, no Maxnodes cap needed) | Sims + point clouds, parked, JazibTD_home.808; library 0.1.0 |
| 11 | TC-10 POP_branching ("last, or never": run last in this window after TC-09 passed) | **pass** | notes []; 0 errors on tips / alloc / trail / look / dep_mat; two scans back to back in one workgroup ran clean (no device error, no hang, 1 024 / 4 096 tips); seed: count 8 at (135, 240), headings 2 pi i / 8 within 3.3e-7; stepped parity from dumped state + trail (the frame texel is the hash salt, mirror run outside TD): 34 frames 20 -> 31 tips and 69 frames 31 -> 103 tips, counts **exact**, tips within 6.1e-5 px, trail within 3e-8; trail sum = closed form within 1e-7 relative (tol 1e-3); no NaN. At Maxtips 4 096 the trail floods the frame (`POP_branching.png`): tuning (Splitrate), not a fault | **4.69 at 540x960 sim, 256 tips, 1080x1920** (deposit Render CPU 1.9; tips 0.34, alloc 0.22, trail 0.53); 1 024: 4.56; 4 096: 4.75 | Sims + point clouds, parked, JazibTD_home.812; library 0.1.0 |

Look note TC-30 (not a fault; **fixed by the Jitter par, 7b**): with Simres = Rays (and 512 / 256) the deposit shows the ray lattice where rays diverge
(`POP_caustics_water.png`, `_water512.png`). Candidates (not built): per-frame hashed jitter of the ray origin inside
its cell with Persist (off for the exact checks) or a small blur in `look`.

Look finding TC-15 (not a check failure; **fixed: birth-capsule binding, 7b**): while dancing, the swarm migrates into a few capsules and stays there (live
after ~6 s: 97 % of 16 k particles in the two feet capsules; numpy mirror 480 frames: 85 % in torso + head). Cause: a
particle a moving limb leaves behind is projected onto the NEAREST capsule, and Respawn 0.02 / s is too slow to
redistribute. Candidates (not built, offline first): Respawn ~0.2-0.5 / s (respawn = uniform rejection sample), or
project onto the capsule the particle was born in (store the capsule index in b1.w).

Window summary (b5 alone, 02:04-02:55Z, 27 Oct): 11 / 11 items pass, no Vulkan device error, no side-TD death, no exec
timeout, no first cook > 1 s (largest 0.57 s), no NaN. Fixes made offline then re-verified live: meshwarp edge clamp
(T-204), crack3d F1 / F2 rename + one hash per cell (T-205), caustics look edge clamp, tubes stage list, rd3d Dist.
Not run (gated, each last in its own window): TC-08 route B (native Particle -> Trail -> Skin POP). Cost: every item
is over the ~3 ms aim except meshwarp / terrain / caustics (2.0-2.4 ms); the Render TOP CPU floor (1.3-1.9 ms under
load ~20-30 with six TDs running, T-198) is most of it; rendering items with a GPU share > 1.5 ms: tree Depth 17
(2.0), tubes (1.7-1.9), crack3d (1.6).

### 7b. Polish lane (27 Oct 2026, b5 -> main, TD 2025.31550)

The three look / cost notes above are fixed (offline tests + live on b5, then by builder in main, parked,
JazibTD_home.826; library 0.1.1). Dumps: `output/checks/polish_b5/`.

- **TC-30 POP_caustics: hashed per-ray jitter.** New par `Jitter` (Rays page, default 1.0, 0 = the old grid): each ray
  starts at its cell centre plus a lowbias hash offset of (cell, frame) inside its own cell (|j| < 0.5 cell, uniform
  `uC5` = Jitter, `absTime.frame`); mirror `pop_caustics_logic.ray_jitter`. Because the offset stays inside the cell, a
  flat refractor at Simres = Rays still lands exactly 1.0 per texel and every sum is unchanged. Live (b5, salt pinned
  to 777): water Amp 0.02 / Freq 6 / Floorsize 4 / Rays 128: sum 16 384 = numpy, max 22 = numpy, L1 0.89 % of N
  (vs the unjittered mirror 28 %, vs salt 778 31 %: the GLSL hash = the numpy hash); flat Rays 64 on Simres 160 (rays
  sparser than texels): lattice spectral peak / mean 3 191 (Jitter 0, = numpy exactly) -> 9.7 (Jitter 1; numpy 9.2,
  34 of 25 600 texels differ by a float32 cell-edge rounding), sum 4 096 both. Cost Rays 256: 2.45 ms (was 2.43).
  One frame of jitter reads as grain, not a grid; Persist (e.g. 0.5) smooths it over frames.
- **TC-15 POP_fillbody: particles stay in the capsule they were born in.** b0.w = capsule k + phase (0.5..1; > 0 still =
  drawn); spawn assigns k = the capsule with the smallest own distance (`owner`), every step projects onto capsule k
  only (analytic normal, the 6-call SDF gradient is gone), a k that is no longer a valid capsule respawns. Mirror
  20 s (4 096, dancing 0.5): capsule shares drift <= 0.006 (old code: 81 % in one foot by 20 s). Live b5 16 384
  pulled 26 s: inside 1.00000 at 0 / 6 / 20 s, own-capsule max d -4.0e-3 (= -Margin), share drift max 0.0045, feet
  0.129 (birth 0.130), no NaN, phase in [0.5, 1). Cost 4.03 ms (was 4.23; state 0.27, was 0.47). Main: Reset pulsed
  while pulled (old states carried phase-only w = capsule 0). **Still open (look, not built):** inside each capsule
  the swarm sits on the skin (outer 30 % of the radius: 0.42 of points at spawn -> 0.99 within ~1 s, frozen body
  too, old code the same): the wander field (speed ~0.18 / s, wavelength ~0.17) is coherent across limbs ~0.03 thick,
  so a whole limb is pushed against one wall. Lower Wander / higher Damp only soften it (Wander 0.3 Damp 10: 0.58);
  bounce instead of slide does not help. Candidate: wander in capsule-local units (scale by radius) or a per-particle
  field offset.
- **TC-09 POP_linegrowth: Render par gate.** `render.par.render = not Lines`, `render_lines.par.render = Lines`: with the
  pane inside the COMP (both viewers on) and Lines off, render_lines fell from 0.97 ms CPU (+0.49 GPU) to 0.04 CPU;
  COMP 7.7 -> 5.0 ms in that view; Lines on: render_lines draws (view_sel = the strip), points render 0.04 CPU. The
  gated op's gpuCookTime stays at its last real value (identical median / p90 every frame), so read it as stale.
