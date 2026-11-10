# Final perf pass, main TD only (27 Oct 2026, TD 2025.31550)

Closing lane. Every side TD (b2, b3, b4, b5, scratch) stopped with `scratch_td.py stop --name <n>` (08:19-08:21; each
saved first), only main running. Earlier partial passes: `PERF_QUIET_27OCT.md` (and its perf lanes 2/3).

## Machine state

- Main TD pid 19303 (`JazibTD_home.828.toe` at start), main watchdog (83947) + side watchdog (2350) running, no side TD.
- `uptime` start 08:27: load 9.46 / 13.82 / 21.64; end 09:53: 7.30 / 6.39 / 5.85 (reruns to 09:58: 7.08). **Much quieter
  than the 00:20 pass (load 40-65)**: these numbers are the best evidence so far, but macOS processes still ran.
- Idle project fps, every lab COMP parked: **59.5** at start and at end (real cooks of `/local/time/clock` over 10 s).
- Network pane on `/project1` the whole time (it was on FX_scope/hud1 before: moved, T-198 / T-201: viewers pull).

## Method

Same driver as PERF_QUIET (scratchpad `pq.py`, kept out of the repo), one COMP at a time, everything else in
/project1/lab parked; `/project1/effectors` cooks as always.
- Un-park, set the documented rest / default pars (same setups as PERF_QUIET: device / network outputs off, AC_audio
  file, BN_fluid2d Testmode, FX_trans Progress 0.5 manual, ...), settle 8 s (6 s for solos; >= 4 s after any slot
  change, T-202 (3)).
- **Racks: "rest" = every slot off**, then each module solo (others 0); generator racks also measured as saved
  ("saved" column). Slots and pars restored afterwards, COMP re-parked (checked: all parked, slots as saved).
- The COMP's Out TOP(s) pulled once a frame with `cook()` (no force) by a self-rescheduling `run(delayFrames=1)`.
- **Real fps** = cooks/s of `/local/time/clock` over 10 s (6 s for solos). **Cook ms** = per frame, sum of cpuCookTime +
  gpuCookTime over the COMP's non-COMP ops that cooked in that frame, median of 140 frames (first 10 dropped).
  "excl." subtracts the Movie File In test-clip / webcam-clip groups (a test input, ~5-6 ms GPU here); the GPU column
  INCLUDES the clip (use it for paired comparisons only). Budget judged on excl.
- No pixel reads, no probe ops, no force cooks, cookRate untouched.
- Reruns (09:54-09:58, T-209): COMPs whose first Out TOP was not the live one (DC_depth_cam, LK_projection_room: now every
  Out TOP pulled; BX_blender_scene has no Out TOP: its Render TOP pulled) and the five fps dips of the first run
  (BL_splat_render 27.2, FX_film rest 25.1 / gate1 16.3, GEN_interactive linevolume1 19.3, GEN_sim ca1 22.3 fps):
  all 59.4-59.5 fps on rerun, so the dips were transient (machine), not the COMPs. The table holds the rerun values.

## Results per COMP (66 lab COMPs + effectors)

| COMP | state | ms excl. clip | ms incl. | CPU | GPU (incl.) | real fps | saved slots ms (fps) | worst solo (ms, GPU) / top ops | 3 ms |
|---|---|---|---|---|---|---|---|---|---|
| AC_audio | default | 0.53 | 0.63 | 0.35 | 0.28 | 59.5 | - | spec_top 0.35, src 0.10 | under |
| AU_db_meter | default | 0.64 | 0.64 | 0.49 | 0.17 | 59.5 | - | bars 0.29, compose 0.14 | under |
| AU_features | default | 0.98 | 1.08 | 1.08 | 0.00 | 59.4 | - | features 0.33, tonal 0.27 | under |
| BJ_urdu_type | default | 3.07 | 3.07 | 0.76 | 2.29 | 59.5 | - | place 1.80, compose 0.46 | OVER |
| BK_dmx_out | default | 0.87 | 0.87 | 0.56 | 0.30 | 59.5 | - | compose 0.36, mon 0.31 | under |
| BK_dmx_patch | default | 1.06 | 1.06 | 0.88 | 0.17 | 59.5 | - | render 1.01, out1 0.04 | under |
| BL_cloud_morph | default | 4.08 | 4.08 | 1.28 | 2.76 | 59.5 | - | render 3.24, post 0.49 | OVER |
| BL_splat_render | default | 6.68 | 6.68 | 1.59 | 5.18 | 59.4 | - | render 5.92, post 0.44 | OVER |
| BN_cloth | default | 5.74 | 5.74 | 2.88 | 2.82 | 59.5 | - | render 1.76, sub_02 0.54 | OVER |
| BN_fluid2d | default | 4.45 | 4.45 | 1.50 | 2.98 | 59.1 | - | fx_press 1.12, fx_advdye 0.75 | OVER |
| BO_particles | default | 2.62 | 2.62 | 1.40 | 1.21 | 59.5 | - | render 1.39, engine 0.53 | under |
| BP_io_router | default | 0.58 | 0.58 | 0.28 | 0.29 | 59.5 | - | test_src 0.17, s1_fit 0.08 | under |
| BX_blender_scene | default | 1.86 | 1.86 | 0.98 | 0.89 | 59.5 | - | render 1.86 | under |
| CQ_cuelist | default | - | - | - | - | 59.5 | - | - | under |
| CV_person_mask | default | 2.12 | 3.27 | 0.69 | 2.36 | 59.4 | - | clip 1.04, matte 0.99 | under |
| DC_depth_cam | default | 1.69 | 7.94 | 0.84 | 7.33 | 59.5 | - | clip 6.27, fx 0.86 | under |
| FT_face_track | default | 0.15 | 1.15 | 0.28 | 0.76 | 59.5 | - | clip 1.00, src_flip 0.06 | under |
| FX_analog | rest | 0.41 | 5.20 | 0.48 | 4.91 | 59.5 | - | crt1 3.47 (GPU 7.78) | under |
| FX_destroy | rest | 0.30 | 5.62 | 0.47 | 5.26 | 59.5 | - | crack1 5.14 (GPU 8.40) | under |
| FX_film | rest | 0.54 | 5.98 | 0.68 | 5.46 | 59.5 | - | dof1 4.31 (GPU 8.32) | under |
| FX_glass | rest | 0.25 | 5.10 | 0.48 | 4.74 | 59.5 | - | liquid1 3.81 (GPU 4.33) | under |
| FX_glitch | rest | 0.55 | 6.63 | 0.64 | 6.17 | 59.5 | - | pixelsort1 6.84 (GPU 7.91) | under |
| FX_haze | default | 0.95 | 0.95 | 0.38 | 0.55 | 59.5 | - | haze 0.55, comp 0.31 | under |
| FX_motion_trail | default | 1.57 | 7.78 | 0.96 | 7.01 | 59.5 | - | clip 6.25, trail 0.56 | under |
| FX_palette_map | default | - | - | - | - | 59.5 | - | - | under |
| FX_retro | rest | 0.45 | 6.58 | 0.57 | 6.17 | 59.4 | - | stitch1 2.33 (GPU 6.13) | under |
| FX_scope | rest | 0.25 | 5.64 | 0.50 | 5.25 | 59.5 | - | lissajous1 3.22 (GPU 9.18) | under |
| FX_strobe | default | 0.72 | 0.72 | 0.45 | 0.24 | 59.5 | - | strobe 0.42, engine 0.16 | under |
| FX_stylise | rest | 0.34 | 6.20 | 0.50 | 5.88 | 59.5 | - | kuwahara1 4.53 (GPU 8.31) | under |
| FX_synth | rest | 0.30 | 5.92 | 0.49 | 5.59 | 59.5 | - | ruttetra1 4.34 (GPU 4.17) | under |
| FX_track | rest | - | - | - | - | 59.5 | - | plexus1 6.44 (GPU 4.41) | under |
| FX_trans | default | 1.94 | 8.71 | 1.30 | 7.97 | 59.5 | - | test_b 5.14, test_a 1.47 | under |
| GEN_clone | default | 3.01 | 3.78 | 1.88 | 1.97 | 59.5 | - | render 2.22, tex_test 0.67 | OVER |
| GEN_interactive | rest | - | - | - | - | 59.5 | saved 4.11 (59.5) | strings1 8.48 (GPU 7.53) | under |
| GEN_pattern | rest | - | - | - | - | 59.5 | saved 1.39 (59.5) | domainwarp1 5.17 (GPU 4.70) | under |
| GEN_points | rest | - | - | - | - | 59.5 | saved 4.70 (59.5) | flame1 4.89 (GPU 3.58) | under |
| GEN_sdf | rest | - | - | - | - | 59.5 | saved 4.92 (59.5) | terrain1 6.18 (GPU 5.68) | under |
| GEN_sim | rest | - | - | - | - | 59.5 | saved 2.06 (59.5) | voronoi1 7.10 (GPU 6.35) | under |
| GN_physarum | default | 6.13 | 6.13 | 2.31 | 3.77 | 59.5 | - | deposit 2.48, fx_agents 1.05 | OVER |
| GN_reaction_diffusion | default | 6.14 | 6.14 | 1.62 | 4.47 | 59.5 | - | fx_rd 3.36, fx_look 1.45 | OVER |
| LK_projection_room | default | 2.85 | 2.85 | 0.80 | 2.05 | 59.5 | - | render 1.61, hud 1.08 | under |
| LK_spectrum_glass | default | 1.30 | 1.30 | 0.35 | 0.96 | 59.5 | - | glass 1.22, out 0.05 | under |
| LK_typecore | default | 0.36 | 0.36 | 0.19 | 0.16 | 59.5 | - | compose 0.27, out 0.05 | under |
| LP_laser_path | default | 5.66 | 5.66 | 1.56 | 4.12 | 59.5 | - | glow_blur 1.68, beam_render 1.26 | OVER |
| LY_lyrics_feed | default | 3.50 | 3.50 | 0.63 | 2.85 | 58.8 | - | over_next 0.81, over_bg 0.79 | OVER |
| MIDI_mapper | default | 0.04 | 0.04 | 0.04 | 0.00 | 59.5 | - | midi_in 0.04 | under |
| MX_prox_material | default | 5.19 | 5.19 | 1.02 | 4.17 | 59.5 | - | render_out 5.02, mx_mat 0.07 | OVER |
| POP_branching | default | 4.04 | 4.04 | 1.36 | 2.66 | 59.5 | - | deposit 1.28, look 0.95 | OVER |
| POP_caustics | default | 3.15 | 3.15 | 1.22 | 1.94 | 59.5 | - | look 1.74, deposit 1.24 | OVER |
| POP_collide | default | 4.59 | 4.59 | 1.57 | 2.99 | 59.5 | - | render 1.96, look 1.75 | OVER |
| POP_crack3d | default | 5.48 | 5.48 | 0.91 | 4.60 | 59.5 | - | render 5.33, out_sel 0.05 | OVER |
| POP_fillbody | default | 6.54 | 6.54 | 1.62 | 4.94 | 59.5 | - | render 3.37, look 1.82 | OVER |
| POP_linegrowth | default | 4.50 | 4.50 | 1.27 | 3.19 | 59.5 | - | render 2.01, look 1.09 | OVER |
| POP_meshwarp | default | 2.04 | 2.04 | 0.99 | 1.03 | 59.5 | - | render 1.86, mat 0.06 | under |
| POP_rd3d | default | 4.07 | 4.07 | 1.72 | 2.27 | 59.5 | - | render 2.12, gs1 0.62 | OVER |
| POP_terrain | default | 1.96 | 1.96 | 0.95 | 1.01 | 59.5 | - | render 1.81, out_sel 0.05 | under |
| POP_tree | default | 3.70 | 3.70 | 1.55 | 2.14 | 59.5 | - | render 1.96, look 0.99 | OVER |
| POP_tubes | default | 5.46 | 5.46 | 1.26 | 4.16 | 59.5 | - | render 3.66, look 1.02 | OVER |
| PV_previz_stage | default | 11.21 | 11.21 | 3.89 | 7.22 | 59.4 | - | bloom 2.69, render 1.99 | OVER |
| PX_lines | default | 3.93 | 3.93 | 1.49 | 2.34 | 59.5 | - | render 1.78, comp 1.01 | OVER |
| PX_pointfx | default | 8.09 | 8.09 | 1.83 | 6.16 | 59.5 | - | srender 5.71, update 0.76 | OVER |
| QC_mcp_checks | default | - | - | - | - | 59.5 | - | - | under |
| TL_timeline | default | 0.27 | 0.27 | 0.27 | 0.00 | 59.5 | - | lanes_eval 0.15, clock 0.09 | under |
| TP_test_pattern | default | - | - | - | - | 59.5 | - | - | under |
| ZC_control_surface | default | - | - | - | - | 59.5 | - | - | under |
| ZK_controls_kit | default | 5.63 | 5.63 | 0.35 | 5.26 | 59.5 | - | noise1 3.02, tint 1.01 | OVER |
| effectors | default | - | - | - | - | 59.5 | - | - | under |

"-" = nothing cooked in the window (0 ops): idle / event-driven COMPs (CQ_cuelist idle, QC_mcp_checks, ZC_control_surface
idle, TP_test_pattern static pattern cooks only on change, FX_palette_map with no input, effectors static rows) and
every rack at rest with all slots off on a generator (GEN_*: nothing to draw) or FX_track (no input picture). FX racks at
rest pass the test clip through for 0.25-0.66 ms.

Every COMP held the project at 59.4-59.5 fps on its own (after the reruns).

## Rack modules solo

**FX_analog** solo (ms excl. test clip / GPU / fps): ntsc1 3.40 / 6.88 / 59.2, vhs1 2.56 / 6.65 / 59.2, signalloss1 1.22 / 4.86 / 59.2, crtfault1 1.12 / 0.80 / 59.2, crt1 3.47 / 7.78 / 59.2, plasma1 2.66 / 7.89 / 59.2

**FX_destroy** solo (ms excl. test clip / GPU / fps): melt1 1.67 / 1.77 / 59.2, burn1 1.29 / 1.34 / 59.2, shatter1 2.32 / 7.29 / 59.2, crack1 5.14 / 8.40 / 59.2, explode1 1.73 / 6.83 / 59.2, disintegrate1 2.97 / 8.36 / 59.2

**FX_film** solo (ms excl. test clip / GPU / fps): tonecurve1 1.71 / 1.68 / 59.2, stock1 0.72 / 6.00 / 59.2, halation1 2.56 / 6.27 / 59.2, grain1 1.71 / 4.76 / 59.2, leaks1 1.59 / 6.68 / 59.2, ca1 1.36 / 6.90 / 59.2, diffusion1 2.30 / 6.85 / 59.2, streak1 1.27 / 6.66 / 59.2, flare1 2.22 / 7.58 / 59.2, star1 3.31 / 9.15 / 59.2, camera1 3.03 / 8.90 / 59.2, dof1 4.31 / 8.32 / 59.2, gate1 1.14 / 6.17 / 59.5, colour1 1.49 / 6.58 / 59.2

**FX_glass** solo (ms excl. test clip / GPU / fps): liquid1 3.81 / 4.33 / 59.2, foil1 1.45 / 2.11 / 59.2, rain1 3.56 / 4.20 / 59.2, frost1 2.83 / 8.45 / 59.2, floor1 2.72 / 8.51 / 59.2

**FX_glitch** solo (ms excl. test clip / GPU / fps): smear1 3.13 / 6.91 / 59.2, block1 2.52 / 7.52 / 59.2, pixelsort1 6.84 / 7.91 / 59.2, dct1 3.79 / 8.03 / 59.3, bits1 1.56 / 7.39 / 59.2, chroma1 1.33 / 7.47 / 59.2, mosaic1 2.58 / 4.20 / 59.2, mosh1 4.08 / 5.66 / 59.2, moshcut1 0.64 / 5.91 / 59.2, timedisplace1 1.76 / 6.89 / 59.2, timeshuffle1 2.28 / 8.11 / 59.2, feedbackkill1 2.83 / 8.00 / 59.2, slash1 1.50 / 6.72 / 59.2, ghost1 3.48 / 6.57 / 59.2, misc1 1.58 / 6.91 / 59.3, databend1 4.15 / 5.18 / 59.2

**FX_retro** solo (ms excl. test clip / GPU / fps): palette1 2.17 / 5.91 / 59.2, dither1 1.58 / 7.22 / 59.1, glyph1 1.74 / 6.92 / 59.2, teletext1 1.84 / 7.12 / 59.2, smalldisplay1 2.22 / 8.16 / 59.2, pixelart1 1.83 / 2.43 / 59.2, scaler1 1.76 / 7.49 / 59.2, stitch1 2.33 / 6.13 / 59.2, ps11 1.07 / 5.65 / 59.2, retroscreen1 1.03 / 6.50 / 59.2, cycle1 1.17 / 6.71 / 59.2, halftone1 1.80 / 7.64 / 59.2

**FX_scope** solo (ms excl. test clip / GPU / fps): xy1 3.16 / 3.26 / 59.2, vector1 2.83 / 8.51 / 59.2, lissajous1 3.22 / 9.18 / 59.2, scopes1 1.51 / 6.79 / 59.2, hud1 1.52 / 6.48 / 59.2

**FX_stylise** solo (ms excl. test clip / GPU / fps): outline1 4.38 / 6.45 / 59.2, boil1 2.34 / 2.80 / 59.2, ink1 3.93 / 8.66 / 59.2, saber1 2.31 / 2.83 / 59.2, clean1 4.16 / 6.36 / 59.2, watercolour1 2.42 / 6.27 / 59.2, engrave1 1.14 / 5.76 / 59.2, kuwahara1 4.53 / 8.31 / 59.2

**FX_synth** solo (ms excl. test clip / GPU / fps): colorize1 1.29 / 6.57 / 59.2, bands1 1.26 / 6.71 / 59.2, keyer1 2.11 / 3.38 / 59.2, ruttetra1 4.34 / 4.17 / 59.2, scanimate1 2.93 / 8.44 / 59.2, vfeedback1 2.42 / 7.27 / 59.2, modulate1 0.97 / 6.32 / 59.2

**FX_track** solo (ms excl. test clip / GPU / fps): plexus1 6.44 / 4.41 / 59.2, hud1 2.37 / 1.72 / 59.2, analytics1 4.41 / 3.67 / 59.2

**GEN_interactive** solo (ms excl. test clip / GPU / fps): ribbon1 3.60 / 2.74 / 59.2, flowers1 7.93 / 6.98 / 59.2, pigment1 3.47 / 2.57 / 59.2, linevolume1 5.45 / 4.58 / 59.5, strings1 8.48 / 7.53 / 59.2, parallax1 2.92 / 2.05 / 59.2, skinner1 3.92 / 3.29 / 59.2

**GEN_pattern** solo (ms excl. test clip / GPU / fps): truchet1 2.02 / 1.45 / 59.2, opart1 1.22 / 0.73 / 59.2, wallpaper1 2.19 / 1.67 / 59.3, domainwarp1 5.17 / 4.70 / 59.2, gyroid1 1.83 / 1.34 / 59.2, cymatics1 1.17 / 0.68 / 59.2, split1 2.25 / 1.79 / 59.2, barcode1 1.14 / 0.69 / 59.2, columns1 2.08 / 1.61 / 59.2, kaleido21 1.10 / 0.67 / 59.2, droste1 1.62 / 1.16 / 59.2, infzoom1 1.40 / 1.00 / 59.2, fireworks1 2.44 / 1.63 / 59.2, bokeh1 3.50 / 2.84 / 59.2, beams1 4.30 / 3.66 / 59.2, moltenchrome1 2.11 / 1.52 / 59.3, caustic1 3.30 / 2.71 / 59.2

**GEN_points** solo (ms excl. test clip / GPU / fps): density2d1 3.36 / 2.03 / 59.2, attractor3d1 4.83 / 3.33 / 59.2, streamlines1 3.95 / 2.53 / 59.2, form1 4.13 / 2.54 / 59.1, flame1 4.89 / 3.58 / 59.1, lsystem1 3.61 / 2.26 / 59.2, graph1 3.22 / 1.97 / 58.8, sparkle1 3.63 / 2.23 / 59.2, polytope4d1 3.06 / 1.75 / 59.2, hyperspace1 4.41 / 3.05 / 59.0, mirrorball1 3.08 / 1.70 / 59.2, nbody1 4.51 / 3.18 / 59.2

**GEN_sdf** solo (ms excl. test clip / GPU / fps): scene1 5.87 / 5.24 / 59.2, fractal1 5.25 / 4.69 / 59.2, fractal2d1 6.11 / 5.51 / 59.2, aurora1 3.04 / 2.52 / 59.2, sky1 3.39 / 2.89 / 59.2, planet1 3.34 / 2.80 / 59.2, ocean1 2.82 / 2.31 / 59.2, cloud1 4.18 / 3.69 / 59.2, blackhole1 4.17 / 3.58 / 59.2, terrain1 6.18 / 5.68 / 59.2

**GEN_sim** solo (ms excl. test clip / GPU / fps): ca1 2.05 / 1.58 / 59.5, voronoi1 7.10 / 6.35 / 59.2, dla1 5.05 / 4.47 / 59.2, blobs1 3.25 / 2.96 / 59.2, lic1 6.72 / 6.31 / 59.2, ripple1 2.98 / 2.54 / 59.2, lavalamp1 3.16 / 2.57 / 59.2, sand1 2.77 / 2.35 / 59.2

## Still over 3 ms (ranked, excl. test clip)

1. PV_previz_stage 11.21 ms (CPU 3.89 / GPU 7.22; top: bloom, render) - several render passes at 1920x1080 aa4 (render, bloom, haze, crowd); Quality / Msaa pars are the lever
2. GEN_interactive.strings1 8.48 ms (CPU 0.98 / GPU 7.53; top: strings1, gi_mask) - per-pixel loop over the point set
3. PX_pointfx 8.09 ms (CPU 1.83 / GPU 6.16; top: srender, update) - sprite Render TOP (srender 5.7 ms, mostly GPU) at Quality high with the saved look; T-143 / T-124
4. GEN_interactive.flowers1 7.93 ms (CPU 0.94 / GPU 6.98; top: flowers1, pts_tex) - per-pixel loop over the point set
5. GEN_sim.voronoi1 7.10 ms (CPU 0.74 / GPU 6.35; top: voronoi1, out1) - per-pixel cell search
6. FX_glitch.pixelsort1 6.84 ms (CPU 0.83 / GPU 7.91; top: pixelsort1, test_clip) - sort passes
7. GEN_sim.lic1 6.72 ms (CPU 0.41 / GPU 6.31; top: lic1, out1) - LIC taps
8. BL_splat_render 6.68 ms (CPU 1.59 / GPU 5.18; top: render, post) - splat Render TOP (5.9 ms) at the doc defaults (Maxsplats 0 = all of the loaded scene); Maxsplats / Thinstep are the lever
9. POP_fillbody 6.54 ms (CPU 1.62 / GPU 4.94; top: render, look) - Render TOP floor + look pass (T-198)
10. FX_track.plexus1 6.44 ms (CPU 1.89 / GPU 4.41; top: plexus1, det) - tracker det / cells passes + line drawing
11. GEN_sdf.terrain1 6.18 ms (CPU 0.52 / GPU 5.68; top: terrain1, drive) - raymarch
12. GN_reaction_diffusion 6.14 ms (CPU 1.62 / GPU 4.47; top: fx_rd, fx_look) - Steps 8 dispatches (dispatch-bound small grid, T-199 (3)); Steps is the lever
13. GN_physarum 6.13 ms (CPU 2.31 / GPU 3.77; top: deposit, fx_agents) - 262k agents; deposit = Render TOP floor (T-198)
14. GEN_sdf.fractal2d1 6.11 ms (CPU 0.55 / GPU 5.51; top: fractal2d1, drive) - raymarch
15. GEN_sdf.scene1 5.87 ms (CPU 0.63 / GPU 5.24; top: scene1, drive) - raymarch
16. BN_cloth 5.74 ms (CPU 2.88 / GPU 2.82; top: render, sub_02) - render + 16 substeps (dispatch-bound, T-199 (3))
17. LP_laser_path 5.66 ms (CPU 1.56 / GPU 4.12; top: glow_blur, beam_render) - preview chain Level / Blur / Composite at 1080x1920 + beam Render TOP (Previewon was on; the preview-off cost was not measured)
18. ZK_controls_kit 5.63 ms (CPU 0.35 / GPU 5.26; top: noise1, tint) - demo noise TOP at 1080x1920 (noise1 3.0 GPU); a test COMP, not a show look
19. POP_crack3d 5.48 ms (CPU 0.91 / GPU 4.60; top: render, out_sel) - Worley per-pixel MAT in the render (T-205)
20. POP_tubes 5.46 ms (CPU 1.26 / GPU 4.16; top: render, look) - Render TOP + look pass
21. GEN_interactive.linevolume1 5.45 ms (CPU 0.84 / GPU 4.58; top: linevolume1, gi_mask) - per-pixel loop over the point set
22. GEN_sdf.fractal1 5.25 ms (CPU 0.62 / GPU 4.69; top: fractal1, drive) - raymarch
23. MX_prox_material 5.19 ms (CPU 1.02 / GPU 4.17; top: render_out, mx_mat) - PBR Render TOP aa2 at 1080x1920 (render_out 5.0)
24. GEN_pattern.domainwarp1 5.17 ms (CPU 0.46 / GPU 4.70; top: domainwarp1, drive) - per-pixel loops (warp octaves / beams / bokeh / caustic taps)
25. FX_destroy.crack1 5.14 ms (CPU 0.68 / GPU 8.40; top: crack1, test_clip) - Source point draws the crack every frame (perf lane 2)
26. GEN_sim.dla1 5.05 ms (CPU 0.61 / GPU 4.47; top: dla1, out1) - walker steps
27. GEN_sdf (saved slots) 4.92 ms (CPU 0.62 / GPU 4.36; top: scene1, drive) - raymarch (scene1)
28. GEN_points.flame1 4.89 ms (CPU 1.28 / GPU 3.58; top: flame1, drive) - module Render TOP floor + its shader (T-198)
29. GEN_points.attractor3d1 4.83 ms (CPU 1.44 / GPU 3.33; top: attractor3d1, drive) - module Render TOP floor + its shader (T-198)
30. GEN_points (saved slots) 4.70 ms (CPU 1.41 / GPU 3.28; top: density2d1, drive) - module Render TOP floor + density pass (T-198)
31. POP_collide 4.59 ms (CPU 1.57 / GPU 2.99; top: render, look) - Render TOP + look pass
32. FX_stylise.kuwahara1 4.53 ms (CPU 0.94 / GPU 8.31; top: test_clip, kuwahara1) - multi-tap / multi-pass filter at 1080x1920
33. GEN_points.nbody1 4.51 ms (CPU 1.29 / GPU 3.18; top: nbody1, drive) - module Render TOP floor + its shader (T-198)
34. POP_linegrowth 4.50 ms (CPU 1.27 / GPU 3.19; top: render, look) - Render TOP + look pass
35. BN_fluid2d 4.45 ms (CPU 1.50 / GPU 2.98; top: fx_press, fx_advdye) - full-res look / advdye bandwidth (perf lane 2)
36. FX_track.analytics1 4.41 ms (CPU 0.73 / GPU 3.67; top: analytics1, cells) - tracker det / cells passes + line drawing
37. GEN_points.hyperspace1 4.41 ms (CPU 1.24 / GPU 3.05; top: hyperspace1, drive) - module Render TOP floor + its shader (T-198)
38. FX_stylise.outline1 4.38 ms (CPU 0.99 / GPU 6.45; top: test_clip, outline1) - multi-tap / multi-pass filter at 1080x1920
39. FX_synth.ruttetra1 4.34 ms (CPU 1.43 / GPU 4.17; top: ruttetra1, test_clip) - needs a compute line rasteriser
40. FX_film.dof1 4.31 ms (CPU 1.21 / GPU 8.32; top: test_clip, dof1) - multi-tap / multi-pass filter at 1080x1920
41. GEN_pattern.beams1 4.30 ms (CPU 0.64 / GPU 3.66; top: beams1, drive) - per-pixel loops (warp octaves / beams / bokeh / caustic taps)
42. GEN_sdf.cloud1 4.18 ms (CPU 0.49 / GPU 3.69; top: cloud1, drive) - raymarch
43. GEN_sdf.blackhole1 4.17 ms (CPU 0.59 / GPU 3.58; top: blackhole1, drive) - raymarch
44. FX_stylise.clean1 4.16 ms (CPU 0.86 / GPU 6.36; top: test_clip, clean1) - multi-tap / multi-pass filter at 1080x1920
45. FX_glitch.databend1 4.15 ms (CPU 0.82 / GPU 5.18; top: databend1, test_clip) - multi-tap / multi-pass filter at 1080x1920
46. GEN_points.form1 4.13 ms (CPU 1.42 / GPU 2.54; top: form1, drive) - module Render TOP floor + its shader (T-198)
47. GEN_interactive (saved slots) 4.11 ms (CPU 0.82 / GPU 3.23; top: ribbon1, pts_tex) - per-pixel ribbon over points
48. BL_cloud_morph 4.08 ms (CPU 1.28 / GPU 2.76; top: render, post) - point Render TOP (3.2 ms)
49. FX_glitch.mosh1 4.08 ms (CPU 0.94 / GPU 5.66; top: test_clip, mosh1) - multi-tap / multi-pass filter at 1080x1920
50. POP_rd3d 4.07 ms (CPU 1.72 / GPU 2.27; top: render, gs1) - Render TOP + gray-scott steps
51. POP_branching 4.04 ms (CPU 1.36 / GPU 2.66; top: deposit, look) - deposit Render TOP + look
52. GEN_points.streamlines1 3.95 ms (CPU 1.42 / GPU 2.53; top: streamlines1, drive) - module Render TOP floor + its shader (T-198)
53. PX_lines 3.93 ms (CPU 1.49 / GPU 2.34; top: render, comp) - Render TOP + comp
54. FX_stylise.ink1 3.93 ms (CPU 0.81 / GPU 8.66; top: test_clip, ink1) - multi-tap / multi-pass filter at 1080x1920
55. GEN_interactive.skinner1 3.92 ms (CPU 0.61 / GPU 3.29; top: skinner1, gi_mask) - per-pixel loop over the point set
56. FX_glass.liquid1 3.81 ms (CPU 0.81 / GPU 4.33; top: liquid1, test_clip) - multi-tap / multi-pass filter at 1080x1920
57. FX_glitch.dct1 3.79 ms (CPU 0.83 / GPU 8.03; top: test_clip, dct1) - multi-tap / multi-pass filter at 1080x1920
58. POP_tree 3.70 ms (CPU 1.55 / GPU 2.14; top: render, look) - Render TOP + look
59. GEN_points.sparkle1 3.63 ms (CPU 1.33 / GPU 2.23; top: sparkle1, drive) - module Render TOP floor + its shader (T-198)
60. GEN_points.lsystem1 3.61 ms (CPU 1.30 / GPU 2.26; top: lsystem1, drive) - module Render TOP floor + its shader (T-198)
61. GEN_interactive.ribbon1 3.60 ms (CPU 0.81 / GPU 2.74; top: ribbon1, pts) - per-pixel loop over the point set
62. FX_glass.rain1 3.56 ms (CPU 0.77 / GPU 4.20; top: test_clip, rain1) - multi-tap / multi-pass filter at 1080x1920
63. GEN_pattern.bokeh1 3.50 ms (CPU 0.66 / GPU 2.84; top: bokeh1, drive) - per-pixel loops (warp octaves / beams / bokeh / caustic taps)
64. LY_lyrics_feed 3.50 ms (CPU 0.63 / GPU 2.85; top: over_next, over_bg) - Over TOP composites of the text layers at 1080x1920 (over_next / over_bg ~0.8 each); not investigated
65. FX_glitch.ghost1 3.48 ms (CPU 0.93 / GPU 6.57; top: test_clip, ghost1) - multi-tap / multi-pass filter at 1080x1920
66. FX_analog.crt1 3.47 ms (CPU 1.06 / GPU 7.78; top: test_clip, crt1) - multi-tap / multi-pass filter at 1080x1920
67. GEN_interactive.pigment1 3.47 ms (CPU 0.92 / GPU 2.57; top: pigment1, pts_tex) - per-pixel loop over the point set
68. FX_analog.ntsc1 3.40 ms (CPU 0.96 / GPU 6.88; top: test_clip, ntsc1) - multi-tap / multi-pass filter at 1080x1920
69. GEN_sdf.sky1 3.39 ms (CPU 0.51 / GPU 2.89; top: sky1, drive) - raymarch
70. GEN_points.density2d1 3.36 ms (CPU 1.28 / GPU 2.03; top: density2d1, drive) - module Render TOP floor + its shader (T-198)
71. GEN_sdf.planet1 3.34 ms (CPU 0.53 / GPU 2.80; top: planet1, drive) - raymarch
72. FX_film.star1 3.31 ms (CPU 1.03 / GPU 9.15; top: test_clip, star1) - multi-tap / multi-pass filter at 1080x1920
73. GEN_pattern.caustic1 3.30 ms (CPU 0.56 / GPU 2.71; top: caustic1, drive) - per-pixel loops (warp octaves / beams / bokeh / caustic taps)
74. GEN_sim.blobs1 3.25 ms (CPU 0.29 / GPU 2.96; top: blobs1, out1) - per-pixel sim pass
75. FX_scope.lissajous1 3.22 ms (CPU 1.15 / GPU 9.18; top: test_clip, lissajous1) - multi-tap / multi-pass filter at 1080x1920
76. GEN_points.graph1 3.22 ms (CPU 1.20 / GPU 1.97; top: graph1, drive) - module Render TOP floor + its shader (T-198)
77. GEN_sim.lavalamp1 3.16 ms (CPU 0.60 / GPU 2.57; top: lavalamp1, out1) - per-pixel sim pass
78. FX_scope.xy1 3.16 ms (CPU 1.04 / GPU 3.26; top: test_clip, xy1) - multi-tap / multi-pass filter at 1080x1920
79. POP_caustics 3.15 ms (CPU 1.22 / GPU 1.94; top: look, deposit) - deposit Render TOP + look
80. FX_glitch.smear1 3.13 ms (CPU 0.87 / GPU 6.91; top: test_clip, smear1) - multi-tap / multi-pass filter at 1080x1920
81. GEN_points.mirrorball1 3.08 ms (CPU 1.29 / GPU 1.70; top: mirrorball1, drive) - module Render TOP floor + its shader (T-198)
82. BJ_urdu_type 3.07 ms (CPU 0.76 / GPU 2.29; top: place, compose) - place GLSL 1.8 ms (perf lane 2: no cheap win)
83. GEN_points.polytope4d1 3.06 ms (CPU 1.30 / GPU 1.75; top: polytope4d1, drive) - module Render TOP floor + its shader (T-198)
84. GEN_sdf.aurora1 3.04 ms (CPU 0.53 / GPU 2.52; top: aurora1, drive) - raymarch
85. FX_film.camera1 3.03 ms (CPU 1.14 / GPU 8.90; top: test_clip, camera1) - multi-tap / multi-pass filter at 1080x1920
86. GEN_clone 3.01 ms (CPU 1.88 / GPU 1.97; top: render, tex_test) - Render TOP floor (render 2.2), 0.01 ms over

Shared reasons: (1) **Render TOP floor** (T-198: ~1-1.3 ms CPU per Render TOP under Rosetta whatever it draws) sets a
~2 ms floor for every POP_*, PX, BL, MX, GN deposit and GEN_points module; the fix is fewer Render TOPs, not render
pars. (2) **Raymarch / per-pixel loops** at 1080x1920 (GEN_sdf, GEN_pattern domainwarp / beams, GEN_sim voronoi / lic,
GEN_interactive flowers / strings): a Quality / resolution par is the lever. (3) **Dispatch-bound small grids**
(GN_reaction_diffusion Steps, BN_cloth substeps, T-199 (3)). (4) Multi-tap FX modules at full res (FX_stylise
kuwahara / outline / ink / clean, FX_film dof, FX_glitch pixelsort / dct / mosh / databend).

Compared with PERF_QUIET (00:20, load 40-65, racks as saved): FX racks at rest are now 0.25-0.66 ms (slot_gate,
T-201); BN_fluid2d 7.92 -> 4.45, BN_cloth 8.34 -> 5.74, LP_laser_path 7.99 -> 5.66, GEN_interactive ribbon1 6.71 -> 3.60,
FX_film halation1 4.05 -> 2.56 / diffusion1 4.26 -> 2.30 (perf lanes 2/3), BO_particles 3.54 -> 2.62 (now under).
Raw JSONL kept in the scratchpad only (`fin_results.jsonl`).

## Perf wave 27 Oct (b3)

Lane perf-b3, build TD **b3** (TD 2025.31550), 10:11-10:55 PKT, load 7-10, b2 busy with the other perf lane. Method as
above (out1 pulled once a frame with `cook()`, per-frame sum of cpu + gpu of the COMP's non-COMP ops, 150-frame
medians after 10 dropped, real fps from b3's frame counter), **network pane on /project1** (a build exec moves it onto
the new ops: every viewer then cooks, T-214), every other lab COMP on b3 parked. b3 numbers run lower than main's
final-pass column (same COMPs, other TD), so before / after are both b3. **Main was not re-measured:** a direct
`td_exec` on main was refused by the session's permission rules after T-212; each COMP reached main by
`bring_home.mjs` (0 errors, parked, saved).

| COMP | main final (ms) | b3 before | b3 after | fps | what changed | 3 ms |
|---|---|---|---|---|---|---|
| PX_pointfx | 8.09 | 6.0-7.5 (srender aa4 3.9-4.8) | **5.1-5.3** (CPU 1.8, GPU 3.3-3.5) | 59.7-59.9 | Look par **Splataa** (srender MSAA, default 1x; aa2 / aa4 / 8x / 16x one click away): aa4 cost 1.3-1.6 ms GPU, aa1 vs aa4 out1 differs no more than two aa4 frames 3 s apart (mean 0.0299 vs 0.0293); **Sorteveryn** default 2 -> 6 (module motion re-sorts ~10 / s; camera moves still re-sort through the camera gate up to Sortmaxhz 20); `perf27_upgrade()` for existing COMPs; panel 432 knobs | over |
| GN_reaction_diffusion | 6.14 | 4.4-4.7 | **2.2-2.3** (CPU 1.4, GPU 0.9) | 59.9 | **Fused steps:** up to 8 Gray-Scott steps per dispatch in shared memory (16 x 16 tile, 8-cell halo, iso + no flow; flow / aniso keep one dispatch per step), new par **Fusesteps** (on; off = the old path); fx_rd 1.38 -> 0.49 ms. out2 bit-exact vs the per-step build (wrap / clamp, spots / centre seeds, 240 steps; Steps 11 + Stopat 243: partial passes), panel 101 knobs | **under** |
| GN_physarum | 6.13 | 4.7-4.8 | **3.8-4.1** (CPU 1.6-1.75, GPU 2.1-2.5; one window 4.9 on a GPU spike) | 58.1-60.0 | 44 engine-reading uniform expressions (~10 us each, Python path) -> ONE `uV[14]` vec4 array from a `uni` Script CHOP (0.09 ms); engine pars cached behind `ph_parwatch` (0.17 -> ~0 ms); out2 / out3 bit-exact after a fixed 30-step run; T-214 | over |

**Still over, and why:**
- **PX_pointfx (~5.2 ms):** the default is the 228 287-splat SmileyPinata scene. srender is vertex-bound (half or
  quarter resolution saved ~0.2 ms; culling every splat after 3 fetches still costs 0.84 ms GPU): ~1.9-2.3 ms GPU +
  the Render TOP CPU floor 0.75 (T-198). Its shader is BL_splat_render's (the other lane's file) behind PX's adapter: a
  per-splat prep pass that would cut the 4x per-vertex work needs that shader restructured (not done). Then update
  0.6-0.8, sort ~0.5 (Sort POP 1.6-2.8 ms per sort, sorter config untouched, T-124), look 0.3, post 0.3. Fewer splats
  (Quality std) would be the next lever but decimates the scan, so it was not taken. px_requirements item 10's own
  target (high 262k <= 6 ms, splats at 60 fps) is met.
- **GN_physarum (~3.9 ms):** the deposit Render TOP (262 144 one-pixel points into 540 x 960 32F with additive
  blending) is 0.63 ms CPU floor + 0.7-1.5 ms GPU; 16F did not help (point-bound); a compute scatter has no float
  atomics on this Mac and a tile-binned raster is linear in N (17.8 ms at 262k, RENDER_COST). Agents 131 072 measured
  4.0 ms (deposit GPU 0.85): changes the network, not taken. The rest: fx_agents 0.46, fx_trail 0.5, fx_look 0.3-0.4,
  engine 0.31 (effectors + engine_step + channel writes).
- **Incidents:** main segfault 16 s after the PX tox bring-home (T-212, not reproduced on b3; PX in main is the new
  version, parked); b3 segfault in a UI thread 8 s after the first RD rebuild (T-213; the staged small-first rebuild then
  ran clean). PX_pointfx's bring-home did not finish its own re-stage + save (the crash), the main autosave / later
  saves (.885 - .901) hold it parked.
- **Also seen:** the RD and physarum zkit panels / COMP viewers pull `preview` and the stats chain whenever the pane is
  inside or on the lab with COMP viewers on (+0.2-3 ms); that is a viewing cost, not a default cost.

## Perf wave 27 Oct (b2)

Lane perf-b2, build TD b2 -> main by `tools/bring_home.mjs`, TD 2025.31550, 10:10-11:15 PKT, load 6-8; b3 (other lane)
running beside it, and in main `FX_track` was un-parked by someone else during the last re-measure (not touched).
Same driver as above (every Out TOP pulled, pane off the COMP, ms = median per-frame cpu + gpu of the COMP's ops), with
the PERF_FINAL setups. GPU columns swing 2x between windows (shared GPU with b3 + main): changes were judged on
same-window A/B and on CPU; parity numbers are pixel reads two execs after the change (T-182).

| COMP | main before | b2 before | b2 after | main after (fps) | What changed |
|---|---|---|---|---|---|
| PV_previz_stage | 11.21 | 8.9-10.6 | 6.7-7.4 | 7.2-8.4 (52-56 fps; idle main 59.0-59.3) | `Bloomres` (Quarter default / Half / Full): the bloom runs on a smaller copy of the hazed image and one `post` GLSL adds it back with exposure at Resx x Resy (replaced `bloom` on Input + Bloom and the `grade` Level TOP); Full = the old picture (out1 mean diff 7.8e-8, max 0.014 = 16F rounding); Quarter vs old: mean 1.3e-4, p99 0, max 0.043. `Bloom` 0 skips the chain. Test noise (Source noise / Input unwired) drawn at 1/4 of the screen texture at the wall aspect, `screen_sel` skips `fit` for it (noise TOP 1.3-1.6 -> 0.35-0.55, fit 0.5-0.8 -> 0). `react_dict` one pass over channels. Builder `_pars` keeps the Zkit page (a rebuild reset Zkd/Zkcols to 56/8; main has 46/12). |
| BL_splat_render | 6.68 | 4.87 | 4.96-5.0 | 5.0-6.4 (58.8-59.5) | `post_sel` skips the post compute when it would only copy (Full render scale, no Bgtop, Bgcolor alpha 0, Outputalpha + Premult on: the defaults): Full parity out1 diff 0.0. New `Renderscale` (Full default, 3/4, 1/2; post upscales, uRes follows the render size): 3/4 saved ~0.6 ms GPU but its upscale costs ~0.45, so Full stays the default. |
| POP_fillbody | 6.54 | 3.2-3.3 | 3.1-3.8 | **2.35-2.72 (59.2-59.3)** | `caps` pass merged into `state`; the capsule table lives in `shared` arrays filled by the first 32 threads of each workgroup (was per-thread arrays, T-187). Twin parity from the same Reset, 150 frames, 16 384 points: max diff 0.0. state + caps 0.7 -> 0.3 ms; stale input wire removed on rebuild. |

**Still over 3 ms, and why:**
- **PV_previz_stage (~7 ms):** CPU alone is ~3.8-4.3 ms of fixed op costs: Render TOP 0.9-1.1 (T-198 floor), `an_chop`
  TOP to CHOP 0.85-0.95 (any download type / colour space / channel count; `immediate` is 4 ms), react + beams Script
  CHOPs ~0.33 each, the crowd sway Noise CHOPs ~0.27 + 0.25 (per sample: Count 100 drops them under 0.16; 800 people is
  the feature), ~15 small TOPs ~0.05-0.15 each. Tried and dropped: numpy and a one-pass pure-Python screen analysis
  (both slower than the built-in sum/max version on 64 px under Rosetta: 130 / 430 us vs 103 us); Quality Medium saved
  only ~0.3 ms (kept High). Next lever: move the crowd sway into the crowd MAT (GPU) and drive beam colours from a
  TOP instead of the TOP to CHOP + Python path. Main fps 52-56 with PV alone cooking vs 59.4 at the 08:27 pass: PV's
  own CPU is unchanged (b2 3.7-3.9 before and after), main had less headroom (FX_track cooking, b2 + b3 beside it).
- **BL_splat_render (~5 ms):** vertex-bound (render at 1/2 size costs about the same as 3/4): 4 vertex invocations per
  splat each redo the full projection / covariance maths for 185-228 k splats. The lever is a per-splat prep pass
  (compute once per splat, the MAT only reads it); the shader is shared with PX_pointfx (px_splat_adapter hooks), so it
  needs both owners: not done here.

Incident: T-215 (b2 SIGBUS in a UI thread 9 s after destroying a 6 MB reference copy the pane showed; relaunched by the
side watchdog; the BL rebuild was redone small-first with the pane on /project1).

## Perf wave 27 Oct (b2, wave 3)

Lane perf-b2-w3, build TD **b2** -> main by `tools/bring_home.mjs`, TD 2025.31550, 19:15-19:37 PKT (load 17-36; the Mac
slept 17:58-19:15 and again from 19:47 in ~15 min cycles, T-219, so later work stopped). Same pull driver as the b2
waves (every Out TOP pulled once a frame, pane on /project1, per-frame cpu + gpu of the COMP's ops, 150-frame medians);
GPU columns swing up to 2x between windows (shared GPU with b3 + main), so changes were judged on parity and same-window
op lists. Main was not exec'd: each COMP went home by tox (0 errors, ops equal) and was checked offline in the saved
main .toe (td_offline) by the ops the change removed.

| COMP | main final | b2 before | b2 after | fps | What changed | 3 ms |
|---|---|---|---|---|---|---|
| PV_previz_stage | 11.21 | 6.7-7.4 (wave 2) | **5.5** | 58.9 | Crowd sway on the GPU: `crowd_tex` -> `crowd_xf` compute (2 buffers) -> TOP instancing; Noise CHOPs `crowd_swz` / `crowd_bob` + `crowd_inst` Merge removed (gone in main .949). Same sway statistics (std, time correlation; twin + tests), not the same random draw. Static parity (Sway 0) mean 2.6e-4, p99 0.0024. react / beams keep their channels. | over |
| LP_laser_path | 5.66 | 2.86 | **2.1-2.6** | 60 | Preview chain: Level + Composite -> one pixel GLSL `persist_add`; 3-input Composite + `bg` Constant -> one compute `preview_comp` (gone in main .955). out2 mean 2e-5, max 0.047 at peaks ~10 (16F order). | under |
| BN_cloth | 5.74 | 5.1-5.3 | 5.6-6.0 all Outs / **4.7** out1 only | 60 | `cloth_mat` reads `state`, so `pos` cooks only when out2 is used (main .963: sampler0top = state). out1 bit-exact. | over |
| MX_prox_material | 5.19 | 5.2 (4.0 GPU) | - | 60 | Not changed (Mac sleep cycle). | over |

**Still over, and why:**
- **PV_previz_stage (~5.5):** render 1.6 (Render TOP floor, T-198), an_chop 0.87 (TOP to CHOP floor), bloom 0.45,
  src_noise 0.37 (test source), react 0.35, crowd_xf 0.3. Beam colours from a TOP were not done: the spill / wash lights,
  the haze uniform and `out_react` need the colours on the CPU, so the download stays either way.
- **BN_cloth (~4.7 with out1 only):** render 1.3-1.5 CPU floor, 16 substeps ~0.5 CPU + ~1.2 GPU, engine 0.37 (reads every
  custom par each frame so expression-driven pars keep working), nrm 0.27. Fused substeps (K per dispatch in shared
  memory) were bit-exact but slower (T-223). Substeps 8 would save ~0.8 ms but changes the motion.
- **MX_prox_material (~5.2):** render_out GPU 4-5 ms that does NOT scale with resolution (108 x 192: same), with Antialias
  aa1, detail normal off (Nrmnear 0) or the env light removed: so it is not pixel work. Suspect: the vertex stage
  (Dispmode swell + Normalfix = 3 proximity evaluations per vertex over the shared effectors list with Ragged noise, on
  ~53k vertices). Next step: A/B Normalfix off / Dispmode none / Effsource explicit, then a per-vertex proximity pass.
- **Library re-export:** not done (needs a live TD; the Mac was sleeping). Due for PV_previz_stage, LP_laser_path,
  BN_cloth and the other COMPs changed today (BL_splat_render, POP_fillbody, PX_pointfx, GN_reaction_diffusion,
  GN_physarum, POP_crack3d, POP_caustics, POP_tubes, POP_rd3d): `td_library_export {path}` (library/ entries are 0.2.0
  from before today's waves).

New LEARNINGS: T-222 (a Blur reading a compute output ~2x; Render Select `bufferindex`; TOP instancing parity), T-223
(fused cloth substeps bit-exact but slower; MAT reads state so the copy pass cooks only when used).

## Perf wave 27 Oct (b3, wave 3)

Lanes perf-b3 (POP, 10:55-11:50) and perf-b3-w3 (resumed after the sleep stalls T-218 / T-219 / T-220; 19:15-00:05),
build TD **b3** (TD 2025.31550) -> main by `tools/bring_home.mjs` (each: 0 errors, ops main = side, parked, saved).
Method as in "Perf wave 27 Oct (b3)": out1 pulled once a frame, per-frame cpu + gpu of the COMP's ops, 150-frame
medians, pane on /project1, everything else parked; old and new measured in **alternating windows** (GPU numbers
swing 2x between windows: b2 and main ran beside it). COMPs not on b3 were loaded from their library tox (exported
after their last builder commit, so = main), which keeps main's par values. **Main was not re-measured** (no direct
exec on main in this lane); b3 runs at ~0.5-0.65x of main's final-pass numbers for the same COMP.
Parity: same frozen state read in separate execs (T-182).

| COMP | main final (ms) | b3 before | b3 after | fps (b3) | what changed | commit |
|---|---|---|---|---|---|---|
| POP_crack3d | 5.48 | 3.66 | 2.3-2.7 | 59.7-60 | back faces culled while nothing can show them (the discard disabled early-z); exact pruned Worley; out1 bit-exact (sphere), torus 2 px / box 13 px at silhouette ties | 7baca5b |
| POP_caustics | 3.15 | 3.0 | 1.75-1.8 | 59.7-60 | look = one write-only buffer; Persist in an acc pass at floor res that cooks only while Persist > 0; bit-exact at defaults, Persist 0.5 max 0.0005 | af279e7 |
| POP_tubes | 5.46 | 3.9 | 2.9-3.3 | 59.7-60 | seam quads clipped (gl_ClipDistance) before raster, out1 bit-exact; new Msaa par (4x default = unchanged, 1x saves ~0.6 GPU) | 372dfb1 |
| POP_rd3d | 4.07 | 3.0 (paired) | 1.45 (solo 1.55) | 59.7-60 | Gray-Scott Steps 1/2/4 in ONE dispatch (shared-memory tile + halo); state bit-exact | f0cb167 |
| POP_collide | 4.59 | 2.14-2.21 | 2.0-2.24 | 60.0 | look = one write-only buffer (main's in-place look instance cooked 1.75 ms, T-216 (1)); Persist > 0 adds a write-only acc pass + Feedback, gated; out1 bit-exact (frozen, Persist 0 and 0.5). b3's old look instance was a fast one, so b3 shows no gain; the gain is main's lottery instance gone | 27adb4c |
| POP_linegrowth | 4.50 | 2.8-4.3 | **0.95-0.99** | 59.7-60 | new Look par **Raster** (compute default / render = old path): `glook` draws the points + tone + over in1 in ONE compute pass (16 x 16 tiles, nodes culled per tile, 1/256 px vertex snap), no Render TOP at the default; Lines keeps the render. vs the Render TOP, same frozen state: Size 1 bit-exact, Size 2 / 8 / zoom 2.5 max 0.008, mean <= 1e-7. CPU 1.0 -> 0.34 | 36ab40b |
| POP_branching | 4.04 | 2.85 | **1.40-1.47** | 60.0 | deposit Render TOP + its geo / MAT / cam removed: `trail` gathers each live tip's deposit per 16 x 16 tile; Diffuse 0 skips the 3 x 3 mean (same value). trail vs a numpy deposit on the same frozen state: r / a exact, g <= 1.3e-8. CPU 1.2 -> 0.4 | 47a8326 |
| ZK_controls_kit | 5.63 | 3.0 | **1.8-2.0** | 60.0 | demo noise gets **Demores** (Half default; Full / Quarter one click, panel knob); with_caption sizes from the caption so out1 stays 1080x1920. Half vs Full frozen: mean 4.4e-4, p99 1/255 | a89c325 |
| BJ_urdu_type | 3.07 | 3.5 | **1.96** | 59.8 | place runs only the words whose box touches its 16 x 16 tile (bit mask, slot order); place g marks pixels near a word, compose runs its 24-tap outline only there. out1 bit-exact (fade, blur + Showboxes, scale + Outlinepx 9). compose GPU 1.9 -> 0.55, place 1.3 -> 0.38 | bc9d13c |

**Not changed, and why (b3 numbers, saved state):**
- **POP_tree 2.06** (render 1.27, segs 0.30, look 0.28): 16 376 dust points at the defaults (Depth 10, Samples 8)
  is above the ~8k compute-raster crossover (RENDER_COST); the tree's points are a 3D projection, the brute-force
  tile walk would cost ~1.7 ms GPU. The Render TOP floor is what is left; under 3 on b3 (main 3.70).
- **BL_cloud_morph 3.95** (5.0-5.3 in a busier window; render 3.1: CPU 0.8, GPU 2.3, post 0.46): 228 287 instanced
  quads. All points culled in the vertex shader still cost 1.46 ms GPU (the per-vertex floor, T-217). Point sprites
  (1 vertex per point) drew the same picture but were SLOWER (8.0 vs 5.0 ms, T-226): reverted. post is not a copy at
  the defaults (it clamps additive alpha > 1), so it cannot be skipped. Levers: fewer points (changes the scan).
- **BN_fluid2d 2.77** (Testmode zero; engine 0.27 CPU, ~11 small compute passes 0.07-0.36 each): under 3 on b3
  (main 4.45). Next lever: the 20 guarded `op('engine')[...]` uniform expressions (~10 us each, T-214) -> one packed
  uniform array as in GN_physarum (~0.2 ms CPU); then merging div / pre / grad around the blocked pressure solve.
- **PX_lines 3.0** (render 1.25, comp 0.65, seg 0.29): its own Render TOP floor; the lever is drawing `lgeo` inside
  PX_pointfx's sprite render (one floor less, RENDER_COST "Per owner"), which is PX-owner work.
- **GEN_clone 2.8 incl. the test clip** (tex_test 0.79 = the card test input; ~2.0 without it; render 1.41): Render
  TOP floor of the instanced cards.
- **LY_lyrics_feed 1.44 median, but 130-436 ms single-frame stalls** at every Urdu line change (b3 fps 37 over 15 s):
  a bitmap Text TOP with readingdirection righttoleft costs ~130 ms per render (LTR 0.5-7 ms, pixel-identical for
  one-line strings, not for wrapped lines; T-225). Fix options (not done: needs wrap detection without the T-76 text
  measurement crash, or the BJ_urdu_type HarfBuzz atlas route): pass lefttoright when the line does not wrap, or
  pre-render lines outside TD.

**Incidents / facts:** T-219 / T-220 (the Mac slept: exec timeouts over-ran 5-30x, b3 and main relaunched), T-221
(a GLSL TOP rebuilt readwrite -> writeonly stayed ~3x slow until one more par change), T-225 (bitmap RTL Text TOP;
feedback-sim copies drift apart: copy-vs-copy is no parity test), T-226 (point sprites slower; `pars()` iteration
hit a broken Par; MAT uniform blocks by name). b3 reference copies (`/project1/perfref`) destroyed one per exec with
the pane on /project1; b3 saved Build3.423, every lab COMP parked.

## Perf wave 28 Oct (b3, wave 4)

Lane perf-b3-w4 (00:05-00:40 PKT 28 Oct), build TD **b3** (TD 2025.31550) -> main by `tools/bring_home.mjs` (each: 0
errors, ops main = side, parked, saved; main checked by an op the change added: `sel_cur` / `txt_next_ur`, `uni`).
LY measured with a per-frame wall-interval sampler (Execute DAT, out1 pulled once a frame, 1800 frames = 30 s, the
rest parked, pane on /project1); BN as in wave 3 (150-frame medians of the COMP's cooked ops), old = the library tox
loaded into `/project1/perfref` (= main), **alternating windows**. Main was not re-measured (no direct exec on main).

| COMP | before (b3) | after (b3) | what changed | parity | commit |
|---|---|---|---|---|---|
| LY_lyrics_feed | Source auto: max frame **585 ms**, p99 127, fps 35.5 (per second 21-38.6), 132 frames > 25 ms; Source manual: max 448 ms, 2 freezes / 30 s | auto: max **17.5 ms**, p99 17.2, fps 60.0 every second, 0 frames > 25 ms; manual: max 18.8, fps 60.0 | the freezes were font face loads, not the RTL renderer (T-228 overturns T-225): per slot a fixed Latin + a fixed Urdu Text TOP and a Switch (no font flip at a line change); osascript spawned with `close_fds=False` (posix_spawn; the fork stalled TD ~120 ms per 4 Hz poll) | out1 bit-exact (max 0.0) in 10 frozen states: demo file at 3 / 6 / 27 / 34 s, a wrap file with 2-3-line Urdu, mixed Urdu + Latin and a wrapped Latin line at cur and next size | 454db44 |
| BN_fluid2d | 2.73-2.76 (Testmode zero); alternating: 3.67-3.96 (CPU 1.24-1.33) | alternating: 3.30-3.51 (CPU 1.05-1.13) | 20 guarded engine-reading uniform expressions on 8 GLSL TOPs -> one `uniform vec4 uV[3]` from a `uni` Script CHOP (as GN_physarum, T-214); GPU swings 2.2-2.7 with the machine in both | fixed 40-step run (Testmode fixed + Stopat): out1 / out2 / fx_advdye / fx_press bit-exact, twice | 5ab06a1 |

**Left / notes:**
- LY: the first Urdu line after a project load still pays one font face load (~130-430 ms): the warm-up force-cook
  was removed after T-227. A later, separate warm-up (e.g. seconds after start, from an exec, not a frame callback)
  could take it; not done.
- LY / BN library tox files were NOT re-exported (the b2 lane owns the library re-exports): `library/LY_lyrics_feed`
  and `library/BN_fluid2d` are older than main.
- **Incidents / facts:** T-227 (b3 segfault in the UI thread ~8 s after the first LY rebuild with new Text / Switch
  TOPs + a frame-start force-cook; looked like a 0.1 % CPU hang: crash dialog pending; rebuilt again parked, then
  un-parked in its own exec: clean), T-228 (font face cache; posix_spawn), T-229 (`numChans` inside a Script CHOP's
  own onCook raises silently: the first uni build froze its uniforms; caught by the Stopat parity run). b3 helpers
  (`/project1/probe_ly`, `/project1/perfref`, `/project1/perf_w4`) destroyed one per exec with the pane on /project1;
  b3 saved Build3.447+, every lab COMP parked.

## Perf wave 27 Oct (b2, wave 4)

Lane perf-b2-w4, build TD **b2** -> main by `tools/bring_home.mjs`, TD 2025.31550, 23:38 27 Oct - 00:45 28 Oct PKT (load
5-36, falling; b3 lane on the GPU beside it; no sleep in the window). Same pull driver as the b2 waves (every Out TOP
pulled once a frame, pane on /project1, per-frame cpu + gpu of the COMP's ops, 150-frame medians); GPU swung ±1-2 ms
between windows, so changes were judged in alternating windows (>= 2 each) with the 10th percentile beside the median,
and the old build was kept as a parked twin (`MX_old`, from the checkpoint tox) for the before / after. Main was not
exec'd: MX went home by tox (478 ops both sides, 0 errors, main `.999`) and main's op list shows the new ops
(`vc_cache`, `vc_rows`, `vc_src`, `vc_slots`, `vc_sop0-2`, `mx_mat_torus`, `mx_mat_sphere`, `mx_pixel_solid`; geo_torus
on `mx_mat_torus`); main par values were equal to b2's before the swap (td_get_pars).

| COMP | main final | b2 before (old twin, same windows) | b2 after | fps | What changed | 3 ms |
|---|---|---|---|---|---|---|
| MX_prox_material | 5.19 | 5.8-7.0 (p10 5.1-5.7) | **4.6** still effectors (CPU 1.0, GPU 3.6; p10 3.9); 5.7-6.3 with a moving list effector | 60 | (1) **Vertex cache** `Dispcache` (on): `vc_cache` compute runs the displacement + Normalfix once per point (53 442) and the vertex shader fetches it by `gl_VertexIndex` when the stored rest point equals its own (else its own path: instancing / skinning / moved parent); per-mesh MATs `mx_mat` / `mx_mat_torus` / `mx_mat_sphere` (slot each). (2) **`mx_pixel_solid`**: no dissolve `discard` while Dissolvemode is off (pdat expression), ~1 ms GPU. (3) **One `mxVertDisp` call site** (loop) shared by both paths. (4) `uMXT` reads time only for ripple / noise / dissolve-speed / normal-speed. Parity: new vs old 2 px (max 2.4e-4, half-float); cache on vs off bit-exact (swell, ripple, push outward, wake), attract 6 px <= 1e-3 | over |

**Still over, and why:**
- **MX_prox_material (~4.6 still, ~6 moving):** Render TOP CPU floor ~1.0 ms (T-198) + per-pixel proximity ~2 ms GPU at
  1080x1920 (w at every pixel's rest position, which every drive needs; it did not scale with pixels and did not move
  with texture-buffer vs uniform reads, ragged noise, detail normal or dead-path stripping: T-230) + ~1.4 ms base PBR
  render. With a moving effector `vc_cache` recooks each frame (0.45 CPU + ~0.7 GPU). The A/B of the previous lane's
  suspects: Normalfix off -1.5 ms, Dispmode off -2.7, Effsource objects ~-1 (all noisy, before the cache); the vertex
  stage was the suspect named, and the pixel stage turned out the larger share.
- No exact shortcut left for the pixel proximity: interpolating w from the vertices changes the look (ragged edge at
  freq 5 on a 0.012 grid), so it was not done.
- First switch to dissolve in a session compiles `mx_pixel` for each MAT (1.6 s once on b2, then 0.003 s).

**Library re-export (wave-3 leftover):** done for PV_previz_stage 0.1.1, LP_laser_path 0.2.1, BN_cloth 0.2.1,
BL_splat_render 0.2.1, POP_fillbody 0.1.2, PX_pointfx 0.6.1, GN_reaction_diffusion 0.1.1, GN_physarum 0.1.1,
POP_crack3d 0.1.1, POP_caustics 0.1.2, POP_tubes 0.1.1, POP_rd3d 0.1.1, POP_collide 0.1.1, POP_linegrowth 0.1.2,
POP_branching 0.1.1 (commit e4242f1; `td_library_export` on main, one at a time, patch versions bumped, each re-parked)
MX_prox_material 0.3.0 after its bring-home, then LY_lyrics_feed 0.1.1 and BN_fluid2d 0.2.1 (b3 wave 4 done). None
was registered by a lane at its export.

New LEARNINGS: T-230. Incidents: none (no crash, no sleep in the window).
