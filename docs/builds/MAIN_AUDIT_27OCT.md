# MAIN_AUDIT_27OCT: main .toe consistency audit (offline, 27 Oct 2026 ~00:50-01:05 PKT)

User (27 Oct ~00:50): "fix all inconsistencies - main is main", "re-organise and sort all the nodes in main comps",
"splats dont have the modules and all?". This is the **offline audit only** (no TD was contacted; nothing in main or
in any builder was changed). The fix lane works from the ordered list at the end.

## Sources and method

- **Main:** `projects/JazibTD_home.492.toe` (00:49, newest when the audit started), re-checked against
  `JazibTD_home.494.toe` (00:54, saved while the audit ran; delta in A1). TD build 2025.31550.
- **Side saves (newest of each):** b2 `Build2.112.toe` (22:36; b2 down since 22:50), b3 `Build3.135.toe` (00:14),
  b4 `Build4.94.toe` (00:15), b5 `Build5.96.toe` (00:15), scratch `Scratch.toe` (empty project).
- **Library:** every `library/*/<name>.tox` expanded (copies in the session scratchpad) and diffed against main.
- **Tools:** `node test/mcp_client.mjs td_analyze_file` (expands a COPY with TD's toeexpand under
  `output/debug/expand/<sha>/`), then a read-only Python walk of the expanded `.n / .parm / .cparm / .text / .table`
  files: op tree, `cook off` flag (= parked), tiles, stored `jz_stages` plans (pickle in the `.n` `dict` line, decoded
  with a class-blocking unpickler), `slots` tables, State-page par values, effector expressions, `zk_rt` text hashes vs
  `git show <rev>:builders/zkit_rt.py`.

**What the offline route can't read (say so, don't guess):** errors / warnings / cook times (the analyzer reports 0
errors, but that is "none saved", not "none at runtime"); live par values that are expressions (only the last saved
value); whether a module DAT's `.module` is current (T-146). `td_analyze_file` lists 399 "unresolved refs": they are
TD's default `pixeldat` / `computedat` names on GLSL TOPs (`<op>_pixel`, `zk_face_compute`), `/jazib_mcp/handlers`
(lives outside /project1) and the root COMP's opviewer `./out1`: **leads, none is a real break** (checked by pattern).

**Op counts (read this before chasing a mismatch):** TD's count (docs, `bring_home`, library `meta.json`, e.g.
GEN_points 2826, FX_trans 412) includes the internals of every `stage_*` annotate COMP; a `.toe` does not save those,
so the saved count is ~1/4 (GEN_points 687, FX_trans 113). Verified: for 42 of 51 library entries the only files the
`.tox` has and main lacks are `stage_*/annotation/...`, and every other file is identical. **Not a finding.**

## 1. Inventory (`/project1` + `/project1/lab`, main .492)

Saved ops = `.n` files under the COMP (recursive). Parked = `allowCooking` False (`cook off` flag). "Stage plan" =
number of boxes in the stored `jz_stages`. zkit panels = number of `zk_rt` runtimes inside (all old, see F1).
"Layout issues" = tile overlaps / ops outside every box / missing plan at that level only; ops parked in an "Other"
box and nested module COMPs are in H1-H6.

| COMP | type | saved ops (.n) | TD ops (library meta) | direct children | parked | stage plan (boxes) | layout issues | zkit panels (all old zk_rt) | library vs main |
|---|---|---|---|---|---|---|---|---|---|
| `/project1/debug` | COMP:container | 30 | - | 30 | no | 4 | ok | 0 | - |
| `/project1/effectors` | COMP:base | 66 | 181 | 15 | no | - | no stored plan | 1 | same |
| `/project1/lab` | COMP:base | 10277 | - | 62 | no | 8 | 2 overlapping tiles; 1 stage-box overlap | 0 | - |
| `/project1/review_tour` | COMP:base | 87 | - | 37 | no | 4 | ok | 1 | - |
| `/project1/show` | COMP:base | 4229 | - | 8 | no | - | 7 overlapping tiles; no stored plan | 0 | - |
| `/project1/show_rig` | COMP:base | 122 | - | 63 | yes | 7 | ok | 1 | - |
| `/project1/lab/AC_audio` | COMP:base | 82 | 335 | 43 | yes | 6 | ok | 1 | same |
| `/project1/lab/AU_db_meter` | COMP:base | 88 | 410 | 43 | yes | 9 | ok | 1 | same |
| `/project1/lab/AU_features` | COMP:base | 70 | 277 | 23 | yes | 4 | ok | 1 | same |
| `/project1/lab/BJ_urdu_type` | COMP:base | 90 | 366 | 45 | yes | 7 | ok | 1 | same |
| `/project1/lab/BK_dmx_out` | COMP:base | 49 | 256 | 49 | yes | 9 | ok | 0 | same |
| `/project1/lab/BK_dmx_patch` | COMP:base | 98 | 374 | 48 | yes | 7 | 1 stage-box overlap | 1 | same |
| `/project1/lab/BL_cloud_morph` | COMP:base | 90 | 315 | 40 | yes | 6 | ok | 1 | **stale** |
| `/project1/lab/BL_splat_render` | COMP:base | 94 | 313 | 44 | yes | 6 | ok | 1 | **stale** |
| `/project1/lab/BN_cloth` | COMP:base | 152 | 470 | 105 | yes | 9 | ok | 1 | **stale** |
| `/project1/lab/BN_fluid2d` | COMP:base | 145 | 459 | 100 | yes | 10 | ok | 1 | **stale** |
| `/project1/lab/BO_particles` | COMP:base | 102 | 398 | 53 | yes | 9 | ok | 1 | **stale** |
| `/project1/lab/BP_io_router` | COMP:base | 172 | 448 | 127 | yes | 7 | ok | 1 | same |
| `/project1/lab/BX_blender_scene` | COMP:base | 49 | 187 | 22 | yes | 6 | ok | 0 | same |
| `/project1/lab/CQ_cuelist` | COMP:base | 68 | 298 | 23 | yes | 5 | ok | 1 | same |
| `/project1/lab/CV_person_mask` | COMP:base | 92 | 345 | 45 | yes | 6 | ok | 1 | same |
| `/project1/lab/DC_depth_cam` | COMP:base | 75 | 305 | 30 | yes | 5 | ok | 1 | same |
| `/project1/lab/FT_face_track` | COMP:base | 98 | 351 | 51 | yes | 6 | ok | 1 | same |
| `/project1/lab/FX_analog` | COMP:base | 458 | 1930 | 28 | yes | 4 | ok | 6 | same |
| `/project1/lab/FX_destroy` | COMP:base | 445 | 1802 | 33 | yes | 5 | ok | 6 | same |
| `/project1/lab/FX_film` | COMP:base | 940 | 4183 | 54 | yes | 4 | ok | 14 | same |
| `/project1/lab/FX_glitch` | COMP:base | 1059 | 4256 | 55 | yes | 4 | ok | 15 | same |
| `/project1/lab/FX_motion_trail` | COMP:base | 82 | 335 | 35 | yes | 6 | ok | 1 | same |
| `/project1/lab/FX_palette_map` | COMP:base | 66 | 273 | 27 | yes | 4 | ok | 1 | same |
| `/project1/lab/FX_retro` | COMP:base | 353 | 1503 | 42 | yes | 5 | ok | 5 | same |
| `/project1/lab/FX_scope` | COMP:base | 370 | 1727 | 25 | yes | 4 | ok | 5 | same |
| `/project1/lab/FX_strobe` | COMP:base | 66 | 296 | 27 | yes | 5 | ok | 1 | same |
| `/project1/lab/FX_synth` | COMP:base | 429 | 1786 | 28 | yes | 4 | ok | 6 | same |
| `/project1/lab/FX_trans` | COMP:base | 113 | 412 | 33 | yes | 5 | ok | 1 | same |
| `/project1/lab/GEN_clone` | COMP:base | 92 | 345 | 35 | yes | 6 | ok | 1 | same |
| `/project1/lab/GEN_interactive` | COMP:base | 322 | 1449 | 42 | yes | 7 | ok | 4 | same |
| `/project1/lab/GEN_pattern` | COMP:base | 760 | 3359 | 52 | yes | 5 | ok | 12 | same |
| `/project1/lab/GEN_points` | COMP:base | 687 | 2826 | 40 | yes | 5 | ok | 8 | same |
| `/project1/lab/GEN_sdf` | COMP:base | 221 | 1141 | 25 | yes | 5 | ok | 3 | same |
| `/project1/lab/GEN_sim` | COMP:base | 352 | 1594 | 26 | yes | 4 | ok | 5 | same |
| `/project1/lab/GN_physarum` | COMP:base | 140 | 485 | 89 | yes | 10 | ok | 1 | **stale** |
| `/project1/lab/GN_reaction_diffusion` | COMP:base | 123 | 422 | 74 | yes | 8 | ok | 1 | **stale** |
| `/project1/lab/LK_projection_room` | COMP:base | 166 | 511 | 67 | yes | 8 | ok | 1 | same |
| `/project1/lab/LK_spectrum_glass` | COMP:base | 54 | 261 | 15 | yes | 4 | ok | 1 | same |
| `/project1/lab/LK_typecore` | COMP:base | 56 | 263 | 17 | yes | 4 | ok | 1 | same |
| `/project1/lab/LP_laser_path` | COMP:base | 107 | 383 | 60 | yes | 7 | ok | 1 | same |
| `/project1/lab/LY_lyrics_feed` | COMP:base | 68 | 298 | 29 | yes | 5 | ok | 1 | same |
| `/project1/lab/MIDI_mapper` | COMP:base | 22 | 137 | 17 | yes | 5 | ok | 0 | same |
| `/project1/lab/MX_prox_material` | COMP:base | 138 | 411 | 52 | yes | 8 | ok | 1 | **stale** |
| `/project1/lab/PV_previz_stage` | COMP:base | 176 | 498 | 74 | yes | 9 | 1 stage-box overlap | 1 | same |
| `/project1/lab/PX_pointfx` | COMP:base | 202 | 616 | 139 | yes | 13 | 18 overlapping tiles; 6 ops outside every box | 1 | same |
| `/project1/lab/QC_mcp_checks` | COMP:base | 100 | 652 | 9 | yes | - | no stored plan | 0 | same |
| `/project1/lab/TL_timeline` | COMP:base | 244 | 474 | 87 | yes | 10 | ok | 1 | same |
| `/project1/lab/TP_test_pattern` | COMP:base | 71 | 324 | 32 | yes | 6 | ok | 1 | same |
| `/project1/lab/ZC_control_surface` | COMP:base | 61 | 314 | 22 | yes | 6 | ok | 1 | same |
| `/project1/lab/ZK_controls_kit` | COMP:base | 58 | 242 | 13 | yes | 3 | ok | 1 | same |
| `/project1/lab/SR_send_palette`, `SR_send_router`, `SR_send_strobe`, `SR_send_trail` | TOP:select x4 | - | - | - | n/a | in lab plan | ok (show_rig sends, builders/show_rig.py, planned in "Looks + effects" / "Show control + I/O") | - | - |

Totals (main .492): 14 817 saved ops under /project1 (10 277 in /project1/lab; /project1/show 4 229 of which ~4 100
are TD's Basic Widgets palette copy in `show/tools`). 50 lab COMPs, all parked; `/project1/effectors`, `debug`,
`review_tour`, `show` cook (effectors by design: never parked); `show_rig` parked. Rack slots (main):

| Rack | slots (order) | enabled at rest in main | doc says |
|---|---|---|---|
| FX_analog | ntsc, vhs, signalloss, crtfault, crt, plasma (6) | vhs1, crt1 | plasma1 enabled 0; no rack rest rule |
| FX_destroy | melt, burn, shatter, crack, explode, disintegrate (6) | **all 6** | crack / explode docs: "left enabled"; no rack rule |
| FX_film | 14 (camera, dof, ca, diffusion, streak, flare, star, halation, leaks, grain, gate, stock, colour, tonecurve) | none | all enabled 0 |
| FX_glitch | 15 (smear ... feedbackkill, slash, ghost, misc) | chroma1 | per-module docs: enabled 0 |
| FX_retro | palette, dither, glyph, teletext, smalldisplay (5) | palette1 | palette1 enabled 1, rest 0 (match) |
| FX_scope | xy, vector, lissajous, scopes, hud (5) | **all 5** | not stated (H1 check ran "all enabled 0") |
| FX_synth | colorize, bands, keyer, ruttetra, scanimate, vfeedback (6) | none | "slots left enabled 0" (match) |
| GEN_interactive | ribbon, flowers, pigment, linevolume (4) | ribbon1 | ribbon1 (match) |
| GEN_pattern | 12 | truchet1 | truchet1 (match) |
| GEN_points | density2d, attractor3d, streamlines, form, flame, lsystem, graph, sparkle (8) | density2d1 (.492); **flame1 (.494, live lane)** | density2d1 (A1) |
| GEN_sdf | scene, fractal, fractal2d (3) | scene1 | scene1 (match) |
| GEN_sim | ca, voronoi, dla, blobs, lic (5) | ca1 | - |

Every module count matches its doc (FX_film 14, GEN_points 8, FX_destroy 6 incl. disintegrate, FX_glitch incl.
slash / ghost / misc, FX_analog incl. plasma, GEN_interactive 4, GEN_sdf 3, GEN_sim 5, GEN_pattern 12, FX_retro 5,
FX_scope 5, FX_synth 6). FX_trans: Type menu has 28 entries (27 in the compiled bank + mosh). GEN_clone: 1 cloner.
PX_pointfx: v2 + perf_upgrade present (eff_watch / eff_tab_watch / eng_ez / eng_gs / px_dirty / px_tick, `sorter`).

## 2. Findings

Order = position in the fix lane's per-COMP pass (section 3). Risk: L = par / text / layout only, M = rebuild a panel
or module by builder (recompile, frames between execs), H = anything near T-152 (big loads) or a live lane.

### A. State / lanes

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| A1 | GEN_points | A live lane is working in main's GEN_points **without a lane entry**: .494 has it un-parked and `flame1` enabled (density2d1 off); .492 had density2d1 enabled + parked (= doc) | .492 vs .494 diff (`GEN_points.n` flags, `slots.table`, `clock_int` CHOPs); `logs/active_lanes.json` = `{}`; exec.log 19:58Z GEN_pattern / pq probe (closing perf lane) | Fix lane waits for that lane to end; then restore the documented rest (density2d1 enabled, rest 0, parked) or update gen_points.md if the user wants flame1. Remind lanes: `tools/lane.py add` (T-95) | H | 0 (preflight) |
| A2 | FX racks | No single rest-state rule: FX_destroy all 6 on, FX_scope all 5 on, FX_analog vhs+crt on, FX_glitch chroma on, FX_film / FX_synth none on (generators: first module on) | slots tables (section 1) | **User decision.** Proposal: FX racks rest with all slots enabled 0 (rack = clean passthrough when un-parked); generators keep their first module on. Then set + document per rack | L | after 9 |
| A3 | PX_pointfx | `Presetname` says `lattice_collapse` but the stack is KANDA swipe (prox_colour, prox_scale, jitter) | PX_pointfx.parm `Presetname lattice_collapse`; `px_stack` 3 rows; M1-M3 pars = BUILTIN 'KANDA swipe' | Set with D1 (recall a preset by name so the label is true) | L | 33 |

### B. Leftovers

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| B1 | MX_prox_material | 6 default `torus1` SOPs left inside geo COMPs (`eff_box`, `eff_sphere`, `geo_plane`, `geo_sphere`, `geo_torus`, `giz_null`), flags off, tile on top of `shape` | `.../torus1.n` x6; render / display flags only on `shape` | `td_why` each (no refs expected), `safe_destroy` the six, re-flow; builder `prox_mat.py` should delete the default torus when it makes a geo | L | 25 |
| B2 | /project1/show/looks | `test_a`, `test_b` stand-in looks ("delete when real looks exist", tools/build_show_panel.py) | `/project1/show/looks/test_a`, `test_b` | **User decision**: keep until real looks, or retire the morning `show` framework if `show_rig` replaced it | L | user |
| B3 | /project1/show | Old layout convention (`box_*` annotations, 7 tile overlaps, no `jz_stages`); `show/tools` = TD Basic Widgets palette copy (~4.1k saved ops, comment "Do not re-flow or edit inside") | analyzer + walk | Leave `tools` alone; re-flow `show` / `show/mixer` only if the user keeps the framework (B2) | L | user |
| B4 | main (whole) | **No test / probe / lane leftovers in main**: FX_synth_test (destroyed 16:24Z), efftest, rm_ab, ctest_ / ftest_ / tmp_, `*_lane`, `_costprobe`, gi_fps_counter, fps_probe: all absent. The `test_*` / `*_probe` ops that remain are builder-made inputs or compile probes (test_clip / test_chart / test_ramp / test_src / testtone / tex_test / b_test, LK_projection_room probe_*, PX colour_probe / update_probe, TL_timeline `lane_*` = timeline lanes) | name scan + `grep` in builders/ | none | - | - |
| B5 | side TDs | b3 `/project1/fps_probe`, b4 `/project1/gi_fps_counter` (Execute DATs) | side saves | delete on the next side-TD start (side only; main clean) | L | side |
| B6 | /project1 | Root COMP's node viewer points at `./out1`, which doesn't exist | analyzer unresolved `top ./out1` | cosmetic; ignore or point it at `show_rig/out1` | L | end |

### C. COMP vs builder / doc

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| C1 | all racks | Module sets match their docs (section 1). Main is the newest copy of every COMP that also lives in a side TD (C3 / I2) | slots tables; side diffs | none | - | - |
| C2 | GEN_points | b3's copy differs from main only by older custom-par order (Precision / Rays) and panel text positions; main = builder | b3 vs main cparm diff | none (main is right); don't bring GEN_points home from b3 again | - | - |
| C3 | FX_destroy | Main has the T-162 shaders in all 6 modules (= b3); b2 and b4 still hold the pre-T-162 shaders (6-7 `*_compute` texts differ) | side diffs | none in main; see I2 | - | - |
| C4 | FX_synth | b5 `ruttetra1/mat` vec0 saved 120 / 256 / 1.5 vs main 1 / 1 / 1 (last-evaluated values of `parent().par.Lines/Samples/Width` expressions: main never cooked ruttetra since load) | b5 vs main parm | none (expressions identical); re-check on un-park | L | 30 |

### D. PX_pointfx / splats ("splats dont have the modules and all?")

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| D1 | PX_pointfx | Rest state = the perf lane's test look: **Render `sprites`**, 3 modules (KANDA swipe: prox_colour, prox_scale, jitter), `truck.splat`, Quality high. A user opening it sees points, not splats, and few modules. The 30 module types and 13 presets exist (`px_presets`: dissolving_scan, hand_push_cloud, ember_splat, scan_morph(_a/_b), lattice_collapse + the 6 BUILTIN looks) but none of the presets sets `Render`, so recalling one keeps sprites | PX_pointfx.parm (`Render sprites`, `Afile .../truck.splat`, `Quality high`), `px_stack`, `px_presets` | **Two documented states, one exec each, in this order:** (1) *default* = `build()`'s DEFAULT_STACK (prox_push, curl, prox_colour, dissolve_noise; E1 box + E2 null), Render `auto`, Quality `std` (doc X1 "4 modules"); (2) *splat showcase*, stored as a preset `splat_showcase` and left active: recall `ember_splat` (hornedlizard.spz, crop + prox_burn + wind + velocity_streak, trails) or `Alley people fire` on TD's SmileyPinata.spz with **Render `splats`** (auto picks splats for .spz) so S1-S6 show; set `Presetname` to the recalled name (A3). Doc px.md: add a "Rest state in main" line. Parked: costs nothing until the user turns it on (splats 14-20 ms under load, PERF in px.md) | M (stack change = 1 recompile, 80-120 ms) | 33 |
| D2 | PX_pointfx | 6 perf_upgrade ops are in no stage box (`eff_tab_watch`, `eff_watch`, `eng_ez`, `eng_gs`, `px_dirty`, `px_tick`) and pile on each other: 18 tile overlaps; plan has an "Other" stage | stagecheck: 6 outside; overlap pairs | Add them to "2 Engine (CPU, per frame)" in the stored plan (builder `px.py` perf_upgrade should do this too), re-flow | L | 33 |
| D3 | PX_pointfx/sorter | 5 ops, 10 tile overlaps, no plan | walk | flow layout inside `sorter` (no plan needed for 5 ops) | L | 33 |
| D4 | BL_splat_render | Has only an Effectors page, no module stack: nothing tells the user the splat modules live in PX | BL_splat_render.cparm pages: Source Camera Splat Sort Look Audio Output Zkit Effectors | **Pointer, not a rebuild:** COMP comment + an annotate/header line "Splat effect modules (30, stackable): /project1/lab/PX_pointfx, Render = splats"; a read-only `About` page par (or Effectors page label) with the same text; mention in docs/builds/splat (pointcloud.md) + px.md | L | 26 |
| D5 | PX_pointfx | 7 of 13 presets point at git-ignored `research_src/BL_gaussian_splats_pointclouds/samples/*` (nike.splat, hornedlizard.spz; present on this Mac); the rest at `media/demo/splats/truck.splat` (git-ignored) | `px_presets` Afile values; `ls` | none for main; note in px.md that the library copy needs those files | L | docs |

### E. Shared effectors consumers (T-159)

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| E1 | 14 consumers in 9 COMPs | **All 14 still on the OLD expression form** (`X if op(...) is not None else Y`, no lambda): `eff_in.chops` + the 6 `sel_vec` uniforms in BL_cloud_morph (pcmat), BL_splat_render (splatmat), BN_cloth, BN_fluid2d (eff_dye, eff_force), BO_particles (state), FX_destroy (eff_mask), GEN_clone (clones), MX_prox_material (mx_mat), GEN_points attractor3d1 / form1 / graph1 / lsystem1 / sparkle1 / streamlines1 (state). Works today (main had the list first, T-159) but differs from the builder and breaks if `/project1/effectors` is ever rebuilt after them | `.parm` expressions: 0 contain `lambda` | `effectors.attach(<comp>)` one COMP at a time (re-writes EFF_IN_EXPR / sel_expr in the new form), check `eff_in.chops` = eff_rows and one uniform; GEN_points: its 6 modules inside the GEN_points pass | L-M | 20-25, 30, 31, 36 |
| E2 | 7 COMPs | `eff_in` / `eff_none` (+ `eff_field_compute`, `eff_mask` in FX_destroy / BN_fluid2d) sit in a `stage_Other` box: `attach` adds ops but not to the COMP's stage plan | stage_Other contents: BL_cloud_morph, BL_splat_render, BN_cloth, BN_fluid2d, BO_particles, FX_destroy, MX_prox_material | put them in the COMP's input stage in `jz_stages`, delete the Other box, re-flow; builder side: `effectors.attach` should register its ops in the plan (owner's change) | L | same as E1 |
| E3 | GEN_interactive, PX_pointfx, GN_* | Not in the 14: they read the list on the CPU (`eff_rt` / `in_eff`) or own Nulls; nothing to re-attach | no eff_in in these | none | - | - |
| E4 | docs | effectors.md status line says "all 9 consumers"; STATUS says 14 (main has 14) | effectors.md line 7-8 | update effectors.md | L | docs |

### F. zkit panels (T-157 / T-162)

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| F1 | 49 COMPs, 126 panels | **Every `zk_rt` in main is pre-fix** (no `_ensure`: first Recall after a build is a no-op). 116 = zkit perf pass (`c326769`); 8 = the older rollout (`643a043`): AC_audio, FX_palette_map, LK_projection_room, LK_spectrum_glass, LK_typecore, LY_lyrics_feed, TP_test_pattern, ZC_control_surface; 2 custom / older variants: FX_strobe, TL_timeline (`controls/params`) | md5 of 126 `zk_rt.text` vs `git show <rev>:builders/zkit_rt.py` | **Panel-only rebuild** per COMP (`zkit.build_controls(...)` / the builder's panel step, `panel=True` only for the panel), un-park first (T-146), read back one Recall, re-park. Racks: one module panel per exec (FX_glitch 15, FX_film 14, GEN_pattern 12, GEN_points 8). Cheaper alternative if a panel rebuild is too heavy: replace only `controls/zk_rt.text` with `builders/zkit_rt.py` (un-parked, 2 frames, T-146) - same fix, no relayout. TL_timeline / FX_strobe: check what their variant adds before replacing | M | every COMP's pass |
| F2 | BK_dmx_out, BX_blender_scene, MIDI_mapper, QC_mcp_checks | No zkit panel (memory: every COMP's controls = zkit kit) | no `zk_rt` | **User decision** (these are tools / I/O, panel may not be wanted) | L | user |

### G. Stale State stamps (T-155 / T-162)

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| G1 | FX_destroy shatter1, disintegrate1 | Saved stamps: shatter1 Hittime 2225.8 / Resettime 2227.48; disintegrate1 Hittime 2450.05 / Resettime 2549.55 (T-162 says main's stale pars were set to -1; these are later test pulses). Harmless now; after the next relaunch absTime restarts and each becomes one phantom hit / reset when the clock passes it (T-162 open) | `.parm` values | set Hittime / Resettime to -1 (builder default) in all 6 modules before the final save | L | 31 |
| G2 | FX_analog crt1, crtfault1, signalloss1, vhs1 | crt1 Degausstime 1738.33; crtfault1 Degausstime 1745.23, Powertime 1777.15; signalloss1 Hittime 1466 (module cooks until the clock passes, T-162); vhs1 Glitchtime 1253.6 | `.parm` values | set each to -1 (logic defaults: `g('Degausstime', -1.0)` etc.) | L | 32 |
| G3 | FX_trans | Go stamps are at default in main now; the builder issue (after a relaunch a finished Go shows FROM until the next Go) is still open, same for signalloss | State page defaults; T-162 "Other racks" | builder fix later (void future stamps in the expression, T-155 rule); not a main edit | L | later |
| G4 | GEN_sim ca1, ZC_control_surface | `Resetcount 11` / `Nbinds 6, Npresets 2`: counters, not stamps | - | none | - | - |

### H. Layout ("re-organise and sort all the nodes")

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| H1 | /project1/lab | Stage plan predates the evening: **21 COMPs sit in "Other"** (all FX_* racks, GEN_*, PX_pointfx, MX_prox_material, GN_physarum, GN_reaction_diffusion, AU_features, CV_person_mask, BX_blender_scene); 2 tile overlaps (BN_fluid2d / BO_particles on DC_depth_cam); 1 stage-box overlap | lab `jz_stages` decode; tile check | New plan: Controls + tests / Audio + analysis (+ AU_features) / Camera + tracking (+ CV_person_mask) / **FX racks** (FX_analog, FX_destroy, FX_film, FX_glitch, FX_retro, FX_scope, FX_synth, FX_trans) / Looks + effects (as now) / **Generators** (GEN_pattern, GEN_points, GEN_sdf, GEN_sim, GEN_interactive, GEN_clone, GN_physarum, GN_reaction_diffusion) / Sims + point clouds (+ PX_pointfx, MX_prox_material) / Stage + projection + light (+ BX_blender_scene) / Show control + I/O. No "Other". Tiles only, nothing cooks | L | 40 |
| H2 | 7 COMPs | eff ops in an Other box | E2 | with E1 | L | E1 |
| H3 | BP_io_router, GEN_sdf/fractal1, GEN_sdf/scene1 | Empty `stage_Other` box left from an earlier layout | box with no op centre inside | delete the box / drop "Other" from the plan, re-flow | L | per pass |
| H4 | BK_dmx_patch, PV_previz_stage, FX_glitch/feedbackkill1, FX_synth/vfeedback1, FX_synth/ruttetra1 | Stage boxes overlap each other; ruttetra1 also has `fb` on top of `outc` / `outc_compute` | stage-box rectangle test | re-flow with the stored plan (`td_layout` flow) | L | per pass |
| H5 | /project1/effectors, QC_mcp_checks | No stored stage plan (15 / 9 children) | no `jz_stages` | give each a plan (effectors: list + rows / objects / runtime / controls; QC: one box per check group) | L | 1, 13 |
| H6 | review_tour/tour, MX geo internals, PV_previz_stage/crowd | small panel / geo COMPs with stacked tiles (list / view / zk; body / head / legs / torso) | tile check | flow layout; geo COMPs after B1 | L | per pass |
| H7 | every COMP | The re-organise pass itself: section 3 order. FX / GEN racks: flow the rack, then each module COMP (its `controls` panel is rebuilt by F1) | - | `td_layout` flow with the stored plan, capture, check | L | all |

### I. Side TDs, transfer files, library

| # | COMP | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| I1 | side TDs | **Nothing lives only in a side TD.** Every side COMP's op set is a subset of main's; side-only items are `stage_Other` annotate boxes (b2 FX_destroy/explode1, b3 FX_glitch/ghost1, b4 GEN_interactive, b5 FX_synth/ruttetra1 + GEN_sim) and the two probes (B5). Main also has newer effectors objects (capsule1, path1) than b3 / b4 | op-set diff per COMP | none | - | - |
| I2 | b2, b3, b4 | Side TDs hold **older** copies that would regress main if brought home: b2 FX_destroy (pre-T-162, no disintegrate) + FX_film (10 modules); b4 FX_destroy (pre-T-162 shaders); b3 FX_glitch (3 of 15 modules); b3 GEN_points (older pars) | side diffs | never bring these home; clear the side labs (or restart the side TDs empty) once the user agrees | L | side |
| I3 | output/transfer | `.tox` exports older than main: FX_destroy_src.tox (23:23, pre-T-162), GEN_points.tox (23:03, the 977 KB load that froze main, T-152), PX_pointfx.tox (22:36), FX_film.tox (23:30, pre-polish) ... | mtimes vs main changes | never load them into main; delete or move to `output/backups/` after the fix pass | L | end |
| I4 | library (8) | **Stale vs main** (exported 19:45-19:52, before effectors attach / later fixes): BL_cloud_morph, BL_splat_render, BN_cloth, BN_fluid2d, BO_particles, MX_prox_material (main has eff_in / eff_none / zk_gpu_* etc.), GN_physarum, GN_reaction_diffusion (3 texts differ: ph_logic / rd_logic, engine_callbacks, vertex / zk_logic) | file diff library .tox vs main | re-export from main (`td_library_export`, read-only on main) after each COMP's pass | L | per pass |
| I5 | library (all) | After F1 (panel rebuild) every entry differs from main again | - | re-export each COMP at the end of its pass (51 entries) | L | per pass |

### J. Docs / STATUS claims vs main

| # | Where | What's wrong | Evidence | Proposed fix | Risk | Order |
|---|---|---|---|---|---|---|
| J1 | docs/builds/fx_destroy_disintegrate.md | Says "Bring-home NOT done ... Main FX_destroy unchanged since JazibTD_home.382"; main has disintegrate1 (rebuilt by builder in main, T-162) | doc lines 89-93 vs main slots | rewrite the status + "Verified live (main)" line | L | docs |
| J2 | docs/builds/fx_destroy.md (+ library summary) | Title "melt, burn, shatter"; rack has 6 modules | doc line 1; INDEX summary | title / summary -> 6 modules | L | docs |
| J3 | library/INDEX.md summaries | Stale first lines: FX_glitch "smear module (pilot)", FX_analog "`ntsc` module (offline prep)", TL_timeline "phase 2 ... NOT yet run live", PX_pointfx "prepared offline" | INDEX.md | regenerate after docs J1-J2 (export re-reads the doc) | L | docs |
| J4 | docs/builds/effectors.md | "all 9 consumers" (main 14) | E4 | update | L | docs |
| J5 | STATUS.md | "Library: 48 entries (+ the 4 big racks)" = 52; INDEX has 51 rows (all 50 lab COMPs + Effectors) | `library/` | 51 | L | docs |
| J6 | STATUS.md | Points to `docs/builds/PERF_QUIET_27OCT.md`, which doesn't exist yet (closing lane running) | `ls` | check after that lane | L | docs |
| J7 | STATUS.md / T-162 | "stale pars then set to -1" vs saved stamps in main (G1, G2) | G1 | true again after G1 / G2 | L | 31-32 |
| J8 | docs/builds/gen_points.md | Rest state density2d1 (true in .492; .494 = flame1 by the live lane) | A1 | re-check after A1 | L | 36 |
| J9 | docs/builds/px.md | No "rest state in main" line; X1 talks about the 4-module default while main rests on KANDA swipe as sprites | D1 | add after D1 | L | 33 |
| J10 | rack docs | No rack states its rest (enabled) slots except FX_retro / GEN_* / FX_synth | A2 | add after the user's A2 decision | L | after A2 |

**Count by category:** A 3, B 6 (B4 = clean bill), C 4 (3 informational), D 5, E 4, F 2, G 4, H 7, I 5, J 10 = **50 rows**;
**actionable fixes 38** (excluding the informational C1-C4, B4, E3, G4, I1 and the user decisions A2, B2, B3, F2).

## 3. Fix lane: order (one COMP at a time in main, least risk first)

Rules for every step: `python3 tools/lane.py add <COMP> "<label>"` first; `allowCooking = True` on that COMP only
(T-146: module / panel DAT updates need it cooking, wait >= 2 frames); **no tox loads into main** (T-152: everything
by builder, one module / panel per exec, frames between); `td_errors` + a read-back after each exec; re-flow with the
stored plan (`td_layout` flow) and a window capture; re-park; save; `td_checkpoint`; `library export` of that COMP;
`lane.py remove`. Never touch another lane's COMP (check exec.log for the last few minutes first).

| Step | COMP | Work (finding ids) |
|---|---|---|
| 0 | preflight | A1: wait for the unregistered GEN_points / perf lane to finish (exec.log quiet, `active_lanes.json`), confirm main's watchdog, save + checkpoint main |
| 1 | /project1/effectors | F1 panel (it is never parked: panel only, no list edits), H5 plan, re-flow |
| 2-12 | group A, one COMP at a time in this order: MIDI_mapper (no panel), LK_spectrum_glass, LK_typecore, ZK_controls_kit, ZC_control_surface, FX_palette_map, FX_strobe, AU_features, CQ_cuelist, LY_lyrics_feed, TP_test_pattern | F1 panel (LK_*, ZC, FX_palette_map, LY, TP on the oldest runtime; FX_strobe: check its custom variant first), H7 re-flow, library re-export |
| 13 | QC_mcp_checks | H5 plan + re-flow (no panel) |
| 14-19 | group B, one COMP at a time in this order: AC_audio, DC_depth_cam, AU_db_meter, BJ_urdu_type, CV_person_mask, FT_face_track, BK_dmx_out (no panel), BK_dmx_patch, BX_blender_scene (no panel), LP_laser_path, PV_previz_stage, LK_projection_room, TL_timeline, BP_io_router | F1, H3 (BP_io_router) / H4 (BK_dmx_patch, PV_previz_stage) / H6, re-flow; TL_timeline: check its custom `controls/params` zk_rt first |
| 20 | GN_reaction_diffusion | F1, re-flow, I4 re-export (library stale) |
| 21 | GN_physarum | F1, re-flow, I4 |
| 22 | BN_cloth | E1 attach, E2 plan, F1, I4 |
| 23 | BN_fluid2d | E1 (eff_dye, eff_force, eff_in), E2, F1, I4 |
| 24 | BO_particles | E1, E2, F1, I4 |
| 25 | MX_prox_material | B1 (6 torus1), E1, E2, F1, H6, I4 |
| 26 | BL_splat_render | D4 pointer, E1, E2, F1, I4 |
| 27 | BL_cloud_morph | E1, E2, F1, I4 |
| 28 | GEN_clone | E1, F1 |
| 29 | FX_trans | F1 (1 panel), re-flow |
| 30 | GEN_sdf (3) -> FX_retro (5) -> FX_scope (5) -> GEN_interactive (4) -> GEN_sim (5) -> FX_synth (6, C4 / H4) | F1 one module panel per exec, H3 / H4, rack + module re-flow, rest state per A2 |
| 31 | FX_destroy | G1 stamps -> -1 (all 6 modules), E1 / E2, F1 (6 panels), rest state per A2 |
| 32 | FX_analog | G2 stamps -> -1, F1 (6), rest state per A2 |
| 33 | PX_pointfx | D1 default state, then splat showcase preset (left active, Render splats), A3 Presetname, D2 plan for the 6 perf ops, D3 sorter, F1 panel, J9 |
| 34 | FX_film | F1 (14 panels, one per exec), re-flow |
| 35 | FX_glitch | F1 (15), H4 feedbackkill1, re-flow |
| 36 | GEN_pattern (12) then GEN_points (8; E1 x6 modules) | heaviest racks last, quiet main only (T-152 / T-153); restore GEN_points rest (A1 / J8) |
| 37 | show_rig, review_tour | F1 panels (show_rig parked, review_tour cooks), H6 |
| 40 | /project1/lab | H1 new lab plan + re-flow (tiles only) |
| end | docs + cleanup | J1-J10, A2 docs, I3 transfer cleanup, B6, LEARNINGS entry if anything new is hit; STATUS top section |

Step numbers are the "Order" column of section 2.

## 4. Top 10 fixes, in order

1. **Preflight (A1):** a live lane is changing GEN_points in main without a lane entry; wait, then restore / document
   its rest state. Register every fix step with `lane.py`.
2. **Stale stamps (G1, G2):** FX_destroy shatter1 / disintegrate1 and FX_analog crt1 / crtfault1 / signalloss1 / vhs1
   stamps -> -1 (pars only, no recompile). Done inside their COMP's pass, before the final save.
3. **Leftovers (B1):** MX_prox_material's six default `torus1` SOPs (main is otherwise free of test / probe / lane ops).
4. **Effectors (E1, E2):** re-attach all 14 consumers (9 COMPs) to the T-159 lambda form, one COMP at a time; put
   `eff_in` / `eff_none` into a planned stage.
5. **PX_pointfx (D1, A3, D2, D3):** rest state = documented default, then a stored `splat_showcase` look left active
   with **Render splats** + a module stack (ember_splat or Alley people fire), true `Presetname`, plan the 6
   perf_upgrade ops, flow `sorter`.
6. **BL_splat_render pointer (D4):** comment + header / page note "splat effect modules: /project1/lab/PX_pointfx
   (Render splats)".
7. **zkit (F1):** rebuild the panel (panel only) in every COMP: 126 panels, all on a pre-T-157 runtime; small COMPs
   first, rack modules one per exec, GEN_pattern / GEN_points last.
8. **Re-organise every COMP (H3-H7)** in section 3's order: empty Other boxes, stage-box overlaps, plans for
   `/project1/effectors` and QC_mcp_checks.
9. **/project1/lab plan (H1):** add FX racks / Generators stages (21 COMPs in "Other" today), fix the 2 overlaps.
10. **Library + docs (I3-I5, J1-J10):** re-export each COMP after its pass (8 are already stale), fix the disintegrate /
    effectors / STATUS / INDEX claims, then ask the user for A2 (rack rest-state rule), B2 / B3 (morning `show`
    framework) and F2 (COMPs without a zkit panel).
