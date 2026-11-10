# cloth: BN_cloth cloth + jelly COMP (live v1 in main, 26 Oct 2026, TD 2025.31550; jelly fails live, T-87)

`/project1/lab/BN_cloth`. A self-contained cloth sim: a grid of vertices whose state lives in textures and is stepped
by compute-mode GLSL TOPs (T-46/T-47), rendered by displacing a Grid SOP in a GLSL MAT. Spec:
`docs/research/BN_fluid_cloth_sims.md` section 6 (our clean-room design). **No limits** (user rule): open ranges,
no limiter, no warnings. **Status: live v1 in main (26 Oct, 31550; see "Verified live" below: cloth mode verified, jelly mode fails live, T-87).** Lines marked LIVE CHECK were the plan those results answer.

In: `in1` TOP texture, `in2` TOP pin mask (Pins = mask), `in3` CHOP colliders (`x y z r`, one sample per sphere,
fills the free sphere slots), `in4` CHOP wind (`x y z` + optional `strength`, added to the wind), `in5` CHOP audio
(RMS of the first 2 channels; the COMP never touches audio output). Out: `out1` TOP render (Resw x Resh, default
1080x1920), `out2` TOP positions (rgba32float, Gridw x Gridh, xyz + w 1), `out3` CHOP stats (`maxstretch meanstretch
energy nan steps beat burst kicks released`).

## One change from the spec (decided offline, with numbers)
The spec's solver (2 substeps x K = 12 gather-Jacobi iterations) leaves too much stretch: the reference solver
(`cloth_logic`, float64) measured, 64x64 hanging cloth, top pinned, 3 s: **max 111 % / mean 31 %** stretch; 48x48
free drape on a sphere: max 66 % / mean 15 %. So BN_cloth uses **XPBD small steps** (Macklin et al. 2019: many
substeps, one iteration each) plus **tethers** (long-range attachments to the pins, Kim et al. 2012):
| Case (reference solver) | 2 x 12 iterations (spec) | 16 substeps x 1 (ours) | 24 x 1 |
|---|---|---|---|
| 64x64 hanging, top pins, tethers off | 111 % / 31 % | 38 % / 10 % | 19 % / 4.5 % |
| 64x64 hanging, tethers on | - | 0.02 % / 0.0 % | 0.01 % |
| 48x48 drape on sphere r 0.3 (no pins) | 66 % / 15 % | 12 % / 3.0 % | 6.7 % / 1.7 % |
| 48x48 two top corners, tethers on / off | 829 % / 24 % (off) | 0.5 % / 0.02 % (on), 173 % / 6.9 % (off) | |
(max / mean of |len/L - 1| over structural springs.) Same dispatch budget: one compute pass per substep. Each substep
is **one fused pass** (predict + 12-neighbour gather-Jacobi with XPBD compliance + tethers + spheres/floor/friction +
velocity) on a **2W x H rgba32float state texture** (positions left half, velocities right half), so one output is
enough and nothing needs atomics. Jacobi relax default 1.5 (48x48 drape, 24 substeps: mean 1.7 % at 1.5 vs 2.3 % at 1.0). Free cloth
(no pins) has no tethers, so the drape row is the honest quality figure; raise Substeps for stiffer cloth.

## Build (live lane, ~15 min)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/cloth.py').read(), ns)
ns['build']('/project1/lab')                     # smax=32 substep nodes, chain='unrolled'
# after LIVE CHECK P2 passes only: ns['build']('/project1/lab', chain='npasses')   (one substep node)
```
Idempotent, T-70 safe (closes its own controls_window, zkit panel rebuilt in place, `_sd` = safe_destroy, never moves
the pane), no pixel readback in the builder (T-74), plain data in storage (`jz_smax`, T-67). Logic:
`builders/cloth_logic.py` (copied into `cloth_logic`), shaders `builders/glsl/cloth_*.glsl` (copied into Text DATs with
`cloth_logic.glsl_header()` prepended: row indices, stencil, pin modes). 40 offline tests:
`python3 -I -m unittest discover -s test -p 'test_cloth.py'` (~12 s). All 9 shaders also compile with `glslc
--target-env=opengl` against a stub TD preamble (scratch check, not in the repo; not proof for MoltenVK).

## Parameters (custom pages; zkit panel shows all five, pulse `Opencontrols`)
| Page | Pars |
|---|---|
| Sim | Gridw / Gridh (128, vertices), Mode (cloth / jelly), Substeps (16, 1..32 built), Dt (0 = 1/cook rate, never wall clock), Timescale, Gravity xyz (0 -9.8 0), Damping (1/s), Stretch / Shear / Bend compliance (0, 1e-4, 0.05; XPBD, m/N: alpha~ = alpha/dt_sub^2 against 2/m per vertex, m = Mass/(Gridw*Gridh)), Relax (1.5), Shape (jelly 0.1), Mass (1 kg whole cloth), Sizew / Sizeh (m), Orient (vertical hangs in XY / horizontal lies in XZ), Top (y of the top edge / plane), Pins (none / top edge / top corners / 4 corners / mask), Tethers (on), Tetherslack (1.0), Floor + Floory |
| Wind | Windmode (off / constant / noise gusts / audio level / BPM bursts), Wind xyz (0 0 3 m/s2), Windgain, Aero (0.7: share of the wind that acts along the normal), Turbulence (per-vertex noise, 0.5), Turbscale (1/m), Gust (Hz), Bpm, Bpmdiv, Burst (pulse, any mode), Burstforce, Burstdecay, Audiogain, Burstthresh, Burstrefractory |
| Collide | Friction (0..1 of the tangential move on contact), Thickness, Sphere1..4 on + centre xyz + radius |
| Look | Resw / Resh, Cam (front / orbit / top / side), Camdist, Camelev, Orbitspeed, Fov (horizontal), Light xyz, Shading (flat / phong / sheen), Colorfront / Colorback, Texture (checker / in1 / none), Texmix, Texscale, Wire, Bg, Alpha (transparent background, premultiplied) |
| Control | Reset, Pause, Step (one frame while paused), Release (drop all pins, tethers off), Testmode (off / rest = no forces / fixed = 1/60 s, constant wind, no turbulence, no audio, no in3), Seed |
Not in v1 (spec 6.2): mouse collider, self-collision, tearing (FUTURE in the spec), POP backend.

## Network (stages, `layout_stages`)
Controls (zkit + window, `cloth_pulses`) | 1 Inputs (`in1..in5`, `tex_src`, `pin_src` switches with blanks) |
2 Engine (`engine` Script CHOP runs `cloth_logic.step` each frame -> named channels; `uni` Script CHOP -> vec4 array
`uP[18]`, channels x y z w, one sample per row; every compute shader reads it as `samplerBuffer` (texturebuffer, as
face_track)) | 3 Rest + state (`rest` W x H, `state_init` 2W x H, `state_fb` Feedback TOP (top = `state`), `nrm`
frame-start normals for the wind) | 4 Substeps (`sub_01..sub_32` share one compute DAT, `sub_sel` Switch picks
Substeps so only that many cook, `state` Null) | 5 Jelly (`cov_x/y/z` from `state_fb` -> Analyze average -> TOP to CHOP
-> `cov`; read by the engine only in jelly mode, so the chain only cooks then; reading `state_fb`, not `state`, avoids a
cook loop) | 6 Render (`pos` -> `out2`, cooks only when out2 is used; `cloth_mat` GLSL MAT (reads `state`) + `cloth_geo` Grid SOP, `cam`, `render` -> `out1`) |
7 Stats (`stats_tex` -> `st_avg` / `st_max` Analyze -> TOP to CHOP (passthrough colour space) -> `stats` -> `out3`).
Viewers: on everywhere except `sub_02..sub_32` and the jelly chain: a viewer in the open pane makes a TOP cook (T-02),
which would cook unused substeps / jelly every frame. Deliberate exception to the viewers-on rule; tell the user.

## Expected numbers (offline reference solver, float64; live 32F should match within the stated tolerance)
- Rest (Testmode rest): positions stay at rest within 1e-7 for 500 frames; velocities < 1e-12. All pinned: exact.
- Hanging 24x24, top pins, tethers off, 150 frames: mean stretch S2 28.6 %, S4 10.4 %, S8 4.4 %, S16 1.7 %
  (max 95 / 36 / 15 / 5.8 %). Tethers on, S8: max 0.03 %.
- Compliance (16x16, S8): mean 2.9 % (0), 3.3 % (1e-3), 6.4 % (1e-2). XPBD: soft material (0.02) gives 27.0 % at S8,
  25.9 % at S16 (stiffness independent of the step count, as designed).
- Drape 20x20 on sphere (0, 0.3, 0) r 0.3, thickness 0.01: min centre distance 0.31 exactly; x-spread 0.884 m
  (friction 0) vs 0.835 m (friction 1).
- BPM 120, 1 beat: bursts at frames 30, 60, 90, 120; 1 h of frames: 7200 ticks, no drift. Audio kicks every 0.1 s with
  refractory 0.25 s: frames 0, 18, 36, 54.
- Jelly: rotation extraction gives det 1 and R^T R = I within 1e-12; equals the SVD polar factor within 1e-6; a flat
  (rank-2) sheet rotated 50 degrees comes back exact within 1e-6; Shape 0.3 halves a random perturbation in < 10 frames.

## Live verification (in order; report every number; build 31550; save stays with the main session, T-71)
Before: `td_status`; park nothing you did not build; BN_cloth un-parked at the start (the builder does it).
1. **Build + errors:** run the build line; `td_errors {path:/project1/lab/BN_cloth, frames:2}` clean (GLSL compile
   errors show here; line numbers include the generated header: ~30 lines); `td_layout check` ok; `td_health`.
2. **P2 npasses probe (LIVE CHECK, 2 min, scratch COMP `/project1/_probe_cloth_np`, then delete):** one compute GLSL
   TOP, rgba32float 4x4, input a Constant 0, shader `TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), texelFetch(
   sTD2DInputs[0], ivec2(gl_GlobalInvocationID.xy), 0) + vec4(1))`, `npasses = 5`: td_inspect R = 5 means passes chain
   (then a rebuild with `chain='npasses'` is allowed: 1 node instead of 16 cooking), R = 1 means they don't (stay unrolled).
3. **L1 stillness (T-46 class, hard criterion):** Testmode rest, Reset, then `td_record_chop {chop:.../stats, frames:300}`:
   `maxstretch` <= 1e-6 and `energy` <= 1e-9 on all 300 frames, `nan` 0. Any drift = the feedback loop tears.
4. **Orientation + render:** Testmode off, defaults (vertical, top pins, noise wind). `td_screenshot` of `out1`: red
   front / blue back cloth, checker, pinned edge at the TOP of the picture, moving in the wind. Upside down, sheared or
   spiky = Grid SOP uv / rows-cols mapping differs from `cloth_vert.glsl` (fix there: flip t.y or swap rows/cols).
5. **L3 hanging:** Windmode off, Gridw/Gridh 24, Tethers off, Substeps 16, Reset, wait 3 s: `out3` meanstretch
   0.017 +- 20 % (0.014..0.021); Tethers on: maxstretch < 0.005.
6. **L2 parity (numpy):** Testmode fixed, Grid 32x32, Substeps 8, Windmode constant, Reset; after ~2 s set Pause on.
   Read `steps` (frames run = steps / 8, the first is the reset frame). In a SEPARATE td_exec >= 2 frames later (T-74),
   read `op('pos').numpyArray(delayed=True)`; offline run `test_cloth.sim(frames, {...same pars...})` and compare:
   relative L2 < 1e-4 (float32 vs float64); if larger, repeat with 10 frames (< 1e-5 there = drift, not a bug).
7. **L4 sphere:** Orient horizontal, Pins none, Top 1.0, Sphere1 on (0, 0.3, 0, r 0.3), Grid 48, Reset, 5 s: positions
   (separate exec, as in 6) min distance to the centre >= 0.31 - 2e-3; render shows the cloth resting on nothing
   visible (spheres are not drawn in v1).
8. **L6 jelly:** Mode jelly, Pins none, Floor on (y -0.8), Orient horizontal, Shape 0.3; Burst: `energy` peaks then
   < 5 % of the peak within 5 s; the sheet keeps its shape (no collapse). Mode cloth again: `cov` stops cooking
   (td_perf: cov_* 0 cooks).
9. **L7 drivers:** Windmode bpm, Bpm 120: `beat` 1 on 120 frames per 60 s (+-1), bursts visible; Windmode audio with an
   Audio Oscillator CHOP (pulse train 2 Hz, no Audio Device Out) wired to in5: `kicks` +120 in 60 s; `Burst` pulse ->
   one burst in any mode; Release -> cloth falls; Reset -> back on its pins.
10. **Perf (60 fps rule):** other lab COMPs parked, pane on BN_cloth and then off it (T-73): `td_perf` per op over
   240 frames + real fps (debug panel `real_fps_2s` or wall clock between frame starts, not absTime). **Expected
   (estimates, not measured):** each substep ~0.03-0.08 ms GPU at 128x128 and ~0.05-0.1 ms CPU (TD per-node cost;
   FX_strobe's single GLSL TOP was 0.09 CPU + 0.05 GPU), so 16 substeps ~1-1.6 ms CPU + ~1 ms GPU; engine Script CHOP
   0.2-0.4 ms; render 1080x1920 aa4 ~0.3-0.6 ms; whole COMP ~2.5-3.5 ms. **Target <= 3 ms, project 60 fps.** Ladder
   if over: Substeps 16 -> 12 -> 8, antialias aa4 -> aa2, Grid 128 -> 96 -> 64, `chain='npasses'` if P2 passed.
   256x256: expect ~4x the GPU part only (dispatch overhead dominates at 128).
11. **L8 soak:** 10 min defaults: `nan` 0 throughout, `energy` bounded, cook ms flat.
12. **Teardown:** open the controls window, rebuild twice with it open: no crash (T-70). Then `td_tox_save` to
   `output/lab/BN_cloth_v1.tox` (stage-wise, never overwriting); main session saves the project.
Record every bug as a LEARNINGS T-nn at once; fill "Verified live" below with the numbers.

## LIVE CHECK (facts that need TD 2025.31550 / MoltenVK)
- Compute GLSL TOP + Feedback TOP loop stays exact over 300+ frames (L1); compute chain of 16-32 passes sharing one
  compute DAT compiles once and runs (spec open questions 2).
- `npasses` on a compute GLSL TOP chains passes (P2; spec open question 1).
- Array uniform from a CHOP as `texturebuffer` (`samplerBuffer uP`, 18 vec4) in compute: values arrive in row order
  (face_track uses the same path; check one value, e.g. R_GRID.x = Gridw, by a debug write if L1 fails).
- GLSL MAT on 31550: `uniform sampler2D` from the Samplers page readable in the VERTEX shader (vertex texture fetch,
  spec open question 3); `uv[0]` from Grid SOP `texture rowcol` spans 0..1 over the points; Grid SOP `rows` = Gridh
  points, `cols` = Gridw points; TDDeform(vec3) accepts the texture position.
- Geometry COMP does not cull the grid by its SOP bounds when the MAT moves vertices far away (watch L7/L4).
- Switch TOP with 32 inputs connects in order via `inputConnectors[i]` and cooks only the selected chain.
- TOP to CHOP on a 1x1 rgba32float Analyze: `crop full` gives one sample, `outputcolorspace passthrough` keeps raw
  values (energy, stretch are not colours), `downloadtype nextframe` (1 frame latency, no stall).
- Out TOP order on the COMP: out1 render, out2 positions (name order vs position order unverified).
- `cam` rotate order xyz + rx/ry from `cloth_logic.camera_pose` actually looks at the cloth (offline test proves the
  maths for that convention only).
- Script CHOP `engine` reading `op('cov')` (fed from `state_fb`) raises no cook-dependency-loop warning.
- Render TOP alpha with Alpha on is premultiplied (overlay rule); `td_screenshot` flattens alpha (T-12): use td_inspect.

## Verified live
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
26 Oct 2026, TD 2025.31550 (Rosetta), cloth lane, lean v1 (steps 1, 3-6 and 10 done; 2, 7, 9, 11, 12 not run):
- **Build:** `build('/project1/lab')` 32 substep nodes, unrolled; td_errors clean (all 9 shaders compile on MoltenVK);
  layout ok (84 ops, 0 overlaps / back wires). zkit panel 89 knobs (face as glslmultiTOP, T-87 (3)).
- **Bug fixed live:** stats + jelly cov read TOP to CHOP names without the row suffix -> all stats 0 (T-87 (1)).
- **L1 stillness** (Testmode rest, 24x24, 300 frames): maxstretch <= 5.7e-6 (bounded float32 noise at 0.043 m spacing,
  not drift: 4.2e-6 at the end), energy <= 2.9e-10, nan 0. The 1e-6 criterion is too strict for 32F; energy passes.
- **Orientation/render:** red front, checker, pinned edge at the top, waving in noise wind
  (output/project1_lab_BN_cloth_out1_2026-10-26T11-45-43-768Z.png). Camera/uv mapping correct as built.
- **L3 hanging** 24x24 S16, 3 s: tethers off mean 0.0180 (target 0.014..0.021), max 0.061 (ref 0.058); tethers on
  max 7.8e-5 (< 0.005).
- **L2 parity** 32x32 S8 fixed/constant wind: 11 frames rel L2 3.2e-6 (< 1e-5); 121 frames 3.8e-4 (float32 drift).
- **L6 jelly: FAILS live** (T-87 (4)): explodes on `nextframe` cov, frozen on `immediate`. Open; use Mode cloth.
- **Perf** (128x128, S16, 1080x1920, pane on BN_cloth, 4 other lab COMPs cooking): real fps 59.0 (median 16.55 ms,
  28/239 frames > 20 ms) vs 59.8 parked. Per op: 16 substeps 0.46 ms CPU + 1.82 ms GPU (sub_01 0.40 GPU, rest ~0.10),
  engine 0.35, render 0.40 + 0.48 GPU, stats chain ~0.2 + 0.25 GPU, nrm 0.06 + 0.12, pos 0.09: ~1.6 CPU + ~2.9 GPU
  = ~4.5 ms (over the 3 ms aim; ladder: Substeps 12/8, aa2, Grid 96). sub_17..32 do not cook at Substeps 16.
- Note: the sim only steps while out1/stats are pulled (T-87 (2)).

## Perf lane 2 (27 Oct, b2, 31550)
- `cloth_substep.glsl`: the 8x8 group computes the predictions + weights of its tile and a 2-cell halo (12 x 12) once
  into shared memory; the 12-stencil reads them there (144 instead of 832 predict() calls per group, each with the
  turbulence noise). Paired A/B of one substep: GPU 0.91x (the 128 x 128 dispatches are overhead-bound: 16 substeps
  stay ~0.2 ms each); one-step output bit-exact (max diff 0). Stats after the rebuild: nan 0, maxstretch 0.038.
- Profiled, left: engine Script CHOP ~0.5-0.8 ms (par reads 0.13, step 0.04, the rest is Script CHOP overhead), render
  1.7-1.9 ms CPU (Render TOP floor under Rosetta, T-150).
- Home: main BN_cloth rebuilt by builder (0 errors), parked, saved JazibTD_home.720; library 0.2.0.

## Perf wave 3 (27 Oct, b2 -> main, 31550)
- `cloth_mat` samples `state` (left half = positions) instead of the `pos` copy: out1 bit-exact (paused, forced recook);
  `pos` cooks only when out2 is pulled. b2, out1 only: 4.7 ms; every Out pulled (PERF_FINAL method): 5.6-6.0 this window
  (before 5.1-5.3 at lower GPU load), main JazibTD_home.963.
- Tried, not taken: K substeps per dispatch in shared memory (bit-exact, but 1.58 ms GPU for 4 vs ~0.15-0.4 for 4
  singles: halo predictions with value noise cost more than the dispatches, T-223).
- Why it stays over 3 ms at the defaults: render 1.3-1.5 ms CPU (Render TOP floor, T-198), 16 substeps ~0.5 CPU + ~1.2
  GPU, engine Script CHOP 0.37 (reads every custom par each frame so expression-driven pars keep working), nrm 0.27.
  Substeps 8 would cut ~0.8 ms but changes the motion (stiffer / looser cloth), so 16 stays the default.
