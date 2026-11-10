# Perf pass with the other TDs closed (27 Oct 2026, TD 2025.31550, main TD only)

**Superseded by `PERF_FINAL_27OCT.md`** (08:27-09:58, all 66 lab COMPs + effectors, every rack module solo, load 6-14).

First numbers taken with only the main TD running (b2-b5 + scratch stopped with `scratch_td.py stop`, each saved
first; b2 was already down). **Not a quiet machine:** load average stayed ~40-65 from system processes (mobileassetd
~48 %, Spotlight mds ~41 %, WindowServer ~46 %, a Virtualization VM ~70 %, the Claude / Orca apps). Read these as
"other TDs closed", not as best-case numbers.

**Stopped part-way for user work (coordinator, ~01:14).** 35 of 51 COMPs measured (all 12 racks with every module solo,
plus 23 single COMPs). **Not measured, stopped for user work:** ZC_control_surface (in flight, abandoned and restored),
ZK_controls_kit, TL_timeline, LY_lyrics_feed, FX_motion_trail, FX_palette_map, PV_previz_stage, TP_test_pattern,
BL_cloud_morph, BL_splat_render, PX_pointfx, GN_physarum, GN_reaction_diffusion, MX_prox_material, BX_blender_scene,
/project1/effectors; also the planned FX_destroy pass with Auto hits on and the reruns of the low-fps solos (below).

## Machine state

- Main TD pid 19303 (`JazibTD_home.476.toe` loaded), main watchdog (83947) + side watchdog (86462) running.
- `uptime` at start 00:21: load 60.19 / 57.88 / 53.19; at stop 01:14: 56.55 / 40.24 / 40.34 (00:54: 44.71).
- Idle project fps, every lab COMP parked: 59.7 (real frames over 10 s, 00:20).

## Method

- One COMP at a time, everything else in /project1/lab parked (effectors cooking, as always). Un-park; pars set to the
  doc default (device / network outputs forced off: BK_dmx_out Active off, BP_io_router sinks off, CQ_cuelist OSC /
  Arena off, CV_person_mask Vision off, DC_depth_cam / FT_face_track helpers off, AC_audio Source file, PX_pointfx
  Preview off); racks measured as saved ("default" row = the saved enabled slots) and then each slot solo (others 0).
  BN_fluid2d had Testmode on so the fluid moves; FX_trans Progress 0.5 manual.
- The COMP's Out TOP is pulled once a frame by a self-rescheduling `run(..., delayFrames=1)` (`cook()`, no force; one
  pending run at a time). Settle 8 s (6 s for solos) for compiles.
- **Real fps** = cooks/s of `/local/time/clock` (cooks every frame) over 10 s wall (6 s for solos), T-158 (5).
- **Cook ms** = per frame, sum of cpuCookTime + gpuCookTime over the COMP's ops that cooked in that frame (ops found by
  totalCooks over 2 s; In ops excluded, T-157 (2)); one sample per distinct cookAbsFrame; median of 130 frames (first
  10 dropped). "Excl. test clip" subtracts the Movie File In source groups (the rack test clip / stored webcam clip
  decode: 1.5-7 ms of the "incl." number, a test input, not the effect). Budget judged on the excl. number.
- Afterwards every par / slot restored to its saved value and the COMP re-parked. No probe ops were created.
- Script: driver kept out of the repo (scratchpad `pq.py`); results JSONL summarised here.

## Results per COMP (defaults)

| COMP | default ms (excl. test clip) | incl. test clip | p90 | real fps | worst module / op (ms) | 3 ms budget |
|---|---|---|---|---|---|---|
| FX_strobe | 0.69 | 0.69 | 0.79 | 59.7 | strobe 0.42 | under |
| FX_film | 0.48 | 2.83 | 10.24 | 59.7 | dof1 5.04 (solo) | under |
| GEN_sdf | 4.81 | 4.81 | 6.18 | 59.5 | fractal2d1 6.77 (solo) | OVER |
| GEN_sim | 1.93 | 1.93 | 2.77 | 59.7 | voronoi1 7.08 (solo) | under |
| FX_retro | 1.90 | 8.44 | 10.05 | 59.7 | smalldisplay1 2.00 (solo) | under |
| FX_scope | 7.29 | 10.37 | 16.87 | 59.6 | xy1 3.10 (solo) | OVER |
| FX_synth | 0.24 | 5.79 | 7.65 | 59.7 | ruttetra1 4.37 (solo) | under |
| FX_analog | 6.19 | 8.39 | 15.49 | 59.6 | ntsc1 5.99 (solo) | OVER |
| FX_glitch | 2.06 | 5.68 | 10.80 | 59.7 | pixelsort1 5.78 (solo) | under |
| FX_destroy | - (nothing cooked: see notes) | - | - | 59.4 | crack1 6.89 (solo) | - |
| GEN_points | 4.11 | 4.11 | 4.74 | 59.7 | attractor3d1 4.68 (solo) | OVER |
| GEN_pattern | 1.80 | 1.80 | 2.07 | 59.7 | domainwarp1 4.35 (solo) | under |
| GEN_interactive | 6.75 | 6.75 | 7.47 | 59.7 | flowers1 8.38 (solo) | OVER |
| FX_trans | 3.02 | 8.63 | 10.62 | 59.7 | test_b 5.24 | OVER |
| GEN_clone | 3.06 | 4.44 | 4.94 | 59.7 | render 2.19 | OVER |
| BK_dmx_out | 1.47 | 1.47 | 1.90 | 59.7 | mon 0.60 | under |
| BK_dmx_patch | 1.92 | 1.92 | 2.29 | 59.7 | render 1.86 | under |
| CQ_cuelist | 0.10 | 0.10 | 0.12 | 59.3 | out_chop 0.09 | under |
| BN_cloth | 8.34 | 8.34 | 9.48 | 59.6 | render 2.58 | OVER |
| BN_fluid2d | 7.92 | 7.92 | 8.94 | 59.7 | fx_press 4.89 | OVER |
| BO_particles | 3.54 | 3.54 | 4.03 | 59.7 | render 2.21 | OVER |
| BP_io_router | 1.71 | 1.71 | 2.06 | 59.6 | test_src 0.77 | under |
| DC_depth_cam | 1.65 | 6.50 | 8.53 | 59.7 | clip 5.33 | under |
| FT_face_track | 1.39 | 6.84 | 8.69 | 59.3 | clip 5.29 | under |
| CV_person_mask | 1.94 | 6.62 | 11.04 | 59.5 | clip 4.83 | under |
| AC_audio | 1.38 | 1.46 | 3.65 | 59.6 | spec_top 1.13 | under |
| AU_db_meter | 1.10 | 1.10 | 1.25 | 45.0 | bars 0.57 | under |
| AU_features | 1.02 | 1.12 | 1.34 | 59.7 | features 0.35 | under |
| BJ_urdu_type | 3.22 | 3.22 | 4.70 | 59.5 | compose 0.85 | OVER |
| LK_typecore | 1.10 | 1.10 | 2.03 | 55.6 | compose 1.02 | under |
| LK_spectrum_glass | 0.98 | 0.98 | 2.69 | 57.8 | glass 0.88 | under |
| LK_projection_room | 2.35 | 2.35 | 4.96 | 54.4 | render 1.66 | under |
| LP_laser_path | 7.99 | 7.99 | 11.97 | 59.0 | beam_render 2.07 | OVER |
| QC_mcp_checks | - (nothing cooked: see notes) | - | - | 59.4 | - | - |
| MIDI_mapper | 0.04 | 0.04 | 0.05 | 59.6 | midi_in 0.04 | under |


Notes:
- FX_destroy default (all 6 slots enabled as saved, no hit): nothing cooked in the sample window (the modules are
  event-driven: they cook on Trigger / Auto / Progress). Solos below are also the idle-after-enable state; the
  "with hits" pass was not run (stopped). QC_mcp_checks: nothing animates, 0 ops cooking.
- FX_trans: its biggest ops were the test inputs (test_b 5.2 ms, test_a 1.4 ms, in the incl. column); the excl.
  number is the transition itself at Progress 0.5 plus anything not a Movie File In.
- AU_db_meter 45.0 fps, LK_projection_room 54.4, LK_typecore 55.6, LK_spectrum_glass 57.8 fps were measured while load
  rose again (00:54-01:05); their own cook was 1-2.4 ms, so the fps dips are not from them (no rerun: stopped).

## Rack modules solo

**FX_film** solo (ms excl. test clip / fps): tonecurve1 0.76 / 59.4, stock1 1.05 / 59.4, halation1 4.05 / 59.4, grain1 1.86 / 59.4, leaks1 1.67 / 59.5, ca1 1.47 / 59.5, diffusion1 4.26 / 59.4, streak1 1.44 / 59.4, flare1 2.23 / 59.5, star1 2.28 / 59.4, camera1 2.39 / 59.5, dof1 5.04 / 59.5, gate1 1.10 / 59.5, colour1 1.32 / 59.6

**GEN_sdf** solo (ms excl. test clip / fps): scene1 6.44 / 59.5, fractal1 5.00 / 59.5, fractal2d1 6.77 / 59.5

**GEN_sim** solo (ms excl. test clip / fps): ca1 2.00 / 59.5, voronoi1 7.08 / 59.5, dla1 4.32 / 59.4, blobs1 3.81 / 59.5, lic1 6.75 / 59.5

**FX_retro** solo (ms excl. test clip / fps): palette1 1.95 / 59.3, dither1 1.37 / 59.5, glyph1 1.49 / 59.5, teletext1 1.54 / 59.4, smalldisplay1 2.00 / 59.5

**FX_scope** solo (ms excl. test clip / fps): xy1 3.10 / 59.5, vector1 2.65 / 59.5, lissajous1 2.91 / 59.3, scopes1 1.47 / 59.6, hud1 1.45 / 59.5

**FX_synth** solo (ms excl. test clip / fps): colorize1 1.18 / 59.4, bands1 1.15 / 59.5, keyer1 1.90 / 59.5, ruttetra1 4.37 / 59.5, scanimate1 3.31 / 59.6, vfeedback1 2.80 / 29.5

**FX_analog** solo (ms excl. test clip / fps): ntsc1 5.99 / 59.4, vhs1 2.92 / 59.5, signalloss1 1.53 / 59.5, crtfault1 1.49 / 59.5, crt1 3.45 / 59.5, plasma1 3.59 / 59.5

**FX_glitch** solo (ms excl. test clip / fps): smear1 2.84 / 59.5, block1 2.10 / 59.4, pixelsort1 5.78 / 59.5, dct1 3.56 / 59.5, bits1 1.40 / 29.9, chroma1 2.07 / 59.5, mosaic1 2.53 / 59.4, mosh1 4.05 / 59.5, moshcut1 0.54 / 59.0, timedisplace1 1.66 / 59.5, timeshuffle1 2.19 / 56.9, feedbackkill1 1.98 / 51.3, slash1 1.27 / 57.2, ghost1 2.69 / 59.3, misc1 1.26 / 57.3

**FX_destroy** solo (ms excl. test clip / fps): melt1 1.35 / 59.5, burn1 1.01 / 59.5, shatter1 2.09 / 59.5, crack1 6.89 / 59.5, explode1 1.29 / 59.5, disintegrate1 1.91 / 59.5

**GEN_points** solo (ms excl. test clip / fps): density2d1 4.06 / 59.5, attractor3d1 4.68 / 59.5, streamlines1 3.97 / 59.5, form1 3.12 / 59.5, flame1 3.87 / 59.5, lsystem1 4.31 / 59.5, graph1 3.35 / 59.5, sparkle1 2.83 / 59.5

**GEN_pattern** solo (ms excl. test clip / fps): truchet1 1.16 / 59.6, opart1 1.54 / 59.5, wallpaper1 1.35 / 59.5, domainwarp1 4.35 / 59.2, gyroid1 0.98 / 59.5, cymatics1 1.62 / 59.5, split1 2.15 / 59.5, barcode1 1.54 / 59.6, columns1 1.23 / 59.5, kaleido21 1.53 / 59.5, droste1 0.74 / 59.5, infzoom1 1.81 / 59.5

**GEN_interactive** solo (ms excl. test clip / fps): ribbon1 6.71 / 59.5, flowers1 8.38 / 59.5, pigment1 5.81 / 59.5, linevolume1 7.37 / 59.5


Solo fps dips not explained by the module's cook (likely machine load or a compile in the window; reruns were queued
and cancelled when the pass was stopped): FX_synth vfeedback1 29.5, FX_glitch bits1 29.9, feedbackkill1 51.3,
timeshuffle1 56.9, slash1 57.2, misc1 57.3.

## Over the 3 ms budget at defaults, other TDs closed

COMP defaults: GEN_sdf 4.81; FX_scope 7.29; FX_analog 6.19; GEN_points 4.11; GEN_interactive 6.75; FX_trans 3.02; GEN_clone 3.06; BN_cloth 8.34; BN_fluid2d 7.92; BO_particles 3.54; BJ_urdu_type 3.22; LP_laser_path 7.99.

Modules solo over 3 ms: FX_film.halation1 4.05; FX_film.diffusion1 4.26; FX_film.dof1 5.04; GEN_sdf.scene1 6.44; GEN_sdf.fractal1 5.00; GEN_sdf.fractal2d1 6.77; GEN_sim.voronoi1 7.08; GEN_sim.dla1 4.32; GEN_sim.blobs1 3.81; GEN_sim.lic1 6.75; FX_scope.xy1 3.10; FX_synth.ruttetra1 4.37; FX_synth.scanimate1 3.31; FX_analog.ntsc1 5.99; FX_analog.crt1 3.45; FX_analog.plasma1 3.59; FX_glitch.pixelsort1 5.78; FX_glitch.dct1 3.56; FX_glitch.mosh1 4.05; FX_destroy.crack1 6.89; GEN_points.density2d1 4.06; GEN_points.attractor3d1 4.68; GEN_points.streamlines1 3.97; GEN_points.form1 3.12; GEN_points.flame1 3.87; GEN_points.lsystem1 4.31; GEN_points.graph1 3.35; GEN_pattern.domainwarp1 4.35; GEN_interactive.ribbon1 6.71; GEN_interactive.flowers1 8.38; GEN_interactive.pigment1 5.81; GEN_interactive.linevolume1 7.37.

Everything else measured is under 3 ms (excl. test clip). Every measured COMP kept the project at ~59.5 fps on its own
(apart from the dips listed above); the 3 ms budget is what limits running several at once.

## Perf lane 2 (27 Oct 03:30-06:20 PKT, build TD b2, 31550; LEARNINGS T-199)

Not a quiet machine: main + b3/b4/b5/scratch lanes busy, load 17-40. Method: each COMP built on b2 FROM ITS BUILDER
(own copies under `/project1/perf2`, other COMPs parked, network pane on /project1), whole-COMP median of per-frame
cpu + gpu over 140 frames (pull sampler, as above). Shader changes judged by paired same-frame A/B of two copies
(T-145/T-150, GPU column: `cook(force=True)` re-evaluates every Python uniform expression, T-199 (2)); parity /
passthrough checked on b2, then brought home into main by builder one module per exec, parked, saved, library re-export.

| COMP / part | before -> after | how | parity | main / library |
|---|---|---|---|---|
| FX_analog ntsc1 `dec` | GPU 0.38x (module solo 2.24 -> 1.66 ms) | tap weights in shared memory (45b2ba0) | as before (fx_analog_ntsc.md) | .703 / 0.2.0 |
| FX_analog plasma1 | total 0.63-0.80x | codes prepass (45b2ba0) | bit-exact | .703 / 0.2.0 |
| FX_analog vhs1 `fx` | GPU 0.61x | per-row + noise lattice in shared memory (51bf470) | V3 mean 0.258 max 0.75 /255; V4 0 | .703 / 0.2.0 |
| GEN_interactive rack `pts` | 2.8-4.2 -> 0.28-0.40 ms CPU | demo hashes cached + vectorised (dbbd633) | bit-exact (test) | .703 / 0.2.1 |
| GEN_interactive solos (whole COMP) | ribbon1 7.6 -> 3.7, flowers1 10.5 -> 6.3, pigment1 6.4 -> 3.2, linevolume1 8.0 -> 3.5 ms | (the `pts` fix) | - | - |
| BN_fluid2d `fx_press` | 1.06-1.25 -> 0.32-0.42 ms (0.31x; GPU 0.17x) | blocked Jacobi, 8 iterations per dispatch (f0fa3fd) | <= 1 ulp (rel 1.1e-7), wall / wrap / open, 8 and 12 its | .720 / 0.2.0 |
| BN_cloth substeps | GPU 0.91x per substep | shared neighbour predictions (eb2d39d) | bit-exact | .720 / 0.2.0 |
| LP_laser_path Script CHOPs | 2.49 -> 0.93 ms CPU (3 ops) | numpy channel IO (10ad72e) | identical samples (test) | .720 / 0.2.0 |

Measured, no change made (b2, pane elsewhere, loaded): FX_scope all 5 on 5.6 ms (10.5 with the pane on the COMP; beams
0.35-0.73 GPU, ~35 ops at 0.1-0.2 ms each: per-op floor, no single hot spot); BJ_urdu_type 2.1 ms (place 0.66 GPU);
FX_destroy crack1 solo 2.9 ms (fx 2.2 GPU: Source point draws the crack every frame, no cheap exact cut); FX_film solos
halation1 5.3, diffusion1 4.6, dof1 3.3 ms (fx 1.0-1.1 GPU each; these include the previous solo's `ext` tail, T-199
(4)); GEN_clone 3.2 ms (Render TOP 2.3, no Python); BN_fluid2d look 0.96 / advdye 0.83 GPU (full-res bandwidth);
LP preview chain ~2-2.6 ms GPU (Level / Blur / Composite at 1080x1920; a fused pass would change the Blur look).
Not done: BO_particles (b3 render-cost lane on it, 05:18), FX_glitch pixelsort / dct / mosh (lane D), GEN_sdf (lane C2),
FX_trans (b4). crt1: no safe win found. Main-TD re-measure of the changed COMPs at rest: not run (main was never
quiet; the b2 numbers above are the evidence).

## Perf lane 3 (27 Oct 05:55-07:00 PKT, build TD b2, 31550; LEARNINGS T-202)

Load 50-73 (all lanes busy). Method as lane 2; shader / structure changes by paired same-frame A/B of the old copy
(`/project1/perf2/FX_film`, lane 2's build) against a fresh build from the new builders (`/project1/perf3/FX_film`),
both racks pulled every frame in alternating order, test clip playing, module ops summed (GPU + CPU).

| COMP / module | before -> after (paired, ms) | how | parity (b2, chart) |
|---|---|---|---|
| FX_film halation1 | 3.11 -> 1.34 (GPU 0.37x) | pyramid 7 ops -> 2 (pyra 1..4 + pyrb 5..7 in shared memory, atlases); gather at the EXT res (`glow`) + full-res composite (`fx`) | energy equal; HA1 570: 0.0292 -> 0.0289 (mirror 0.0289), light-core peak -3.4 %, 0 px > 4/255; Quality full = old within 1 fp16 ulp |
| FX_film diffusion1 | 4.06 -> 1.63 (GPU 0.32x) | same | DF1 580 0.0112 = 0.0112, energy 1717 -> 1717.4; mist / glimmer energy kept (glimmer sparkle peaks -2 %); quarter dream glow core peak -19 % (energy kept) |
| FX_film dof1 | 2.61 -> 2.09 (GPU 0.75x) | `hl`: one thread per tile for T <= 8 (was one 64-thread workgroup per 4x4 tile) | hl max 6e-5 of 801, out1 max 2.4e-4 (T 4 / 8 / 32) |
| FX_scope (5 on) | ~8.8 -> ~6.4 (sequential, load 54 -> 73) | stale-slow ops recreated by builder (T-202 (2): xy1/look 0.31 -> 0.04-0.07, hud1/fx 0.50 -> 0.18, xy1/path 0.27 -> 0.05-0.08 GPU); hud shader without per-thread arrays (bit-exact, GPU-neutral) | hud bit-exact (4 modes) |

Every pyramid level matches the old pyr1..pyr7 chain within 1 fp16 ulp; Amount 0 with all three on: out = in (0).
Also: FX_film rack got `slot_gate` (T-198 / T-201) + grown-menu refresh (T-190); the T-199 (4) tail is TD-side
(T-202 (3)). FX_scope beams stay ~1.2 ms per module (content; no merge without changing the look).

**Not done (b2 hung, T-202 (4)):** bring-home into main (FX_film halation1 / diffusion1 / dof1 by `_instance`
panel=False + `gate_upgrade` for the other 11 slots; FX_scope: recreate the GLSL TOPs of xy1 / vector1 / lissajous1 /
hud1 by builder), main saves, library re-export. b2 stopped answering during the rehearsal of the in-place module
rebuild on its panel-carrying copy: rehearse that on a side TD again before main. Commits: 82d203f, 1adad79, 3965115.

**Done 27 Oct ~08:05-08:15 PKT (bring-home lane, b2 + main, T-207):** rehearsed clean on b2 (14-module panel copy),
then main: FX_film `JazibTD_home.820` (3 modules rebuilt, 11 gate_upgrade, 14 gates, errors 0), FX_scope
`JazibTD_home.824` (16 GLSL TOPs recreated in 4 modules, errors 0); both parked; library re-exported.
