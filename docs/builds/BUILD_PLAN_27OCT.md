# BUILD_PLAN_27OCT: one merged, ranked build plan (27 Oct 2026, TD 2025.31550 target; offline planning, no TD used)

User (27 Oct): "research more and build more", "everything Ruben Fro does and all", lines / haze / glow / colour / lights /
geometry, 60 fps target (~3 ms per COMP), "dont bloat stuff just for modularity", options + creative liberty, no built-in
limits, main is main. This file merges the four 27 Oct research files and the Ruben Fro waves into **one** list, picks
homes, orders wave 2 and splits the rest into lanes. It replaces the build-order sections of FX7a s6, FX7b s4, FX7c s3,
FX7d s3 and RUBENFRO_COVERAGE s3 waves 2-3 (those stay as the specs; read the row before building it).

Sources (row ids used below): `docs/research/FX7a_shadertoy_glsl_libraries.md` (**SX-nn**), `FX7b_td_creators_2025.md`
(**TC-nn**), `FX7c_other_tools_effects.md` (**7C-nn**), `FX7d_scan_artists.md` (**SAnn**), `docs/builds/RUBENFRO_COVERAGE.md`
(**G/H/GL/CO/L/GE/K** rows), `FX0_effects_backlog.md` (**#nn**). Perf facts: `PERF_QUIET_27OCT.md`. Risk rules: LEARNINGS
T-124 (GPU fault kills the other TDs), T-143 (Script CHOP time dependency, absTime gates), T-152 / T-153 (big .tox loads
freeze main), T-154 (first compile of new shader text freezes 0.5-0.75 s).

**Nothing here is measured.** Every ms is the research file's estimate. Reality check from the quiet perf pass: a GEN_pattern
module whose shader is "0.3 ms" measured **0.74-2.15 ms solo** (rack overhead + 1080x1920 fill), so read every estimate
below as "+0.7-1 ms rack floor". Replace with `td_perf` + real fps at build time.

## 0. State this plan starts from (27 Oct, from git log + build docs)

| Wave-1 lane | State | Gate for wave 2 |
|---|---|---|
| W1-A lights in `/project1/effectors` | **in main** (JazibTD_home.534; library Effectors 0.2.0) | done |
| W1-B palette convention (`px_palette.glsl`, `uPal[16]`) | offline only by design (no live phase; each consumer wires it) | rides wave 2 |
| W1-C `PX_lines` | live on scratch, LC1-LC14 pass (c21314e); doc has **no "In main" section yet** | **pending: build in main by builder** |
| W1-D `FX_haze` + bloom v2 | **in main**, parked (library FX_haze 0.1.0 from .544) | done |
| W1-E geometry + env in BL / MX | **in main** (.542), parked; env capture far over budget (16.2 ms, use only when needed) | done |

Wave 2 starts when W1-C is in main. Machine rules carried in: b2 is out (hung twice, T-148); live TDs = **b3, b4, b5,
scratch**, one lane per TD, **<= 4 live lanes** (drop to 2 after any crash/hang until a clean hour passes; memory rule
"max 2 live TD builders" is the fallback). Bring-homes one at a time across all TDs, in a quiet minute (T-153); a COMP
> ~2000 ops or > ~20 GLSL passes comes home **by builder, one module per exec** (T-152): that is every rack touched here
(GEN_pattern, GEN_sim, GEN_sdf, GEN_points, GEN_interactive, FX_glitch, FX_trans, PX).

## 1. Merged items (duplicates folded)

| Merged item | Rows folded in | Chosen route (why) | Home |
|---|---|---|---|
| **Fireworks** | SX-15, 7C-10 | v1 = analytic per-pixel bursts (SX-15, 0.8-1.4 ms, no state, `Hit` input); shell types (peony / ring / willow / crossette) as burst-shape tables in the same shader. BO Aux-spawn shells (7C-10) only if asked: tail | GEN_pattern.fireworks |
| **Liquid-glass panels / lenses** | SX-01, 7C-23 | 1 GLSL: SDF shapes (<= 8, smooth union) + analytic SDF gradient bevel + 3-tap dispersion + pre-blurred 2nd input + Fresnel rim | FX_glass.liquid |
| **Rain on glass** | SX-02, 7C-34 | drop SDF layers + normal offset + blur-level input (Gerardo MIT port as reference) | FX_glass.rain |
| **Aurora** | SX-13, 7C-13 | 24-50-step curtain march at Quality 0.5 + FSR (SX-10) | GEN_sdf.aurora |
| **Ocean (+ seabed caustics)** | SX-14, 7C-14 | warped-sine height march, Quality 0.5 + FSR; Gerstner as the cheap mode | GEN_sdf.ocean |
| **Caustics** | SX-04 (overlay), TC-30 (thrown by geometry) | SX-04 tileable overlay now; TC-30 Ray-POP version = POP-structural tail | GEN_pattern.caustic; TC-30 -> lane H |
| **Falling sand** | SX-27, 7C-15 | Margolus 2x2 compute at 540x960, materials in rgba8 | GEN_sim.sand |
| **Terrain fly-over** | SX-20 (raymarch), TC-19 (clipmap mesh) | raymarch first (no POP risk); clipmap mesh = POP-structural tail | GEN_sdf.terrain; TC-19 -> lane H |
| **2.5D depth-parallax still** | SX-30, 7C-31, TC-05 | relief-march GLSL (2 inputs: colour + depth), camera sway; depth bands (TC-05) as a mode; depth precomputed per still | GEN_interactive.parallax |
| **Echo ghosts / time-stacked actor** | SA31, TC-37 | one actor ring buffer of K frames; modes `echo` (fade) and `stack` (z offset by age, TC-37) | PX Actormode `echoes` (W3) |
| **Motion blur on points** | SA16, K25 | one velocity term: object delta + camera delta, covariance stretch (S3 path) | PX `velocity_streak` source `delta` (W3) |
| **Trails / light ribbons** | G3 (done in PX_lines), TC-08, SA30 | TC-08 look = **PX_lines `trails` fed by BO_particles' state texture** (standalone PX_lines takes any xyz TOP: no POP work, no new engine); Skin-POP tubes = tail; SA30 = pool `spawn_from edge` (W3) | BO_particles preset `lighttrails` + PX W3 |
| **Plexus / k-NN lace** | TC-01, G5 (done), SA33 | TC-01 = blob-tracker centres -> PX_lines `connect` (no POP); SA33 = PX_lines source `knn` (load-time grid hash) | FX_track.plexus; PX_lines (W3, lines owner) |
| **Distance-field outline / contour echo / neon halo** | SX-06, 7C-05 | JFA distance of any matte (reuse `glsl/gen_sim_vor_jfa.glsl` read-only), modes outline / halo / contour bands (Notch Image Distance) / sticker | FX_stylise.outline |
| **Saber beam on paths / text / masks** | 7C-09 | capsule SDF for polylines + the same JFA for masks; draw-on Start/End | FX_stylise.saber |
| **Stylise rack** | SX-05, SX-07, 7C-01..04, #71 Kuwahara | one rack (see s2) | FX_stylise |
| **Beam fans / virtual laser show** | TC-32, 7C-20 | 2D beam-cone GLSL + feedback advection, modes fans / cones / tunnel / wave lines; paths from `laser_path` later (LP is 7.99 ms, not extended now) | GEN_pattern.beams |
| **Transitions wave 2** | SX-31..35, TC-33, 7C-06, 7C-29, TC-16 | `wrap_gl()` route for SX-31..35 (pick 2 of the signal-failure set, overlaps `tvoff`); TC-33 beat ripple; 7C-06 page flip; 7C-29 jigsaw; TC-16 point morph = tail | FX_trans |
| **Hex / tri mosaic with beat flips** | 7C-33, SX-03 fly-eye cells | lattice cell id + per-cell flip; fly-eye lens stays in FX_glass.frost | FX_glitch.mosaic mode |
| **Strands / spiral vortex** | TC-13, K22 | BO_particles modes `vortex` / `strands` (TC-13); K22 PX strand preset (stretch axis `noise`) stays in PX W3 | BO_particles; PX W3 |
| **Delight + normals** | SA1, SA2, RUBENFRO L1 "normals later" | one load pass (numpy, PCA k=12) writing `nrm` + delit colour | PX W2-2 |
| **Glyph / dab sprites** | K21, SA35 | one Sprite `atlas` mechanism; glyph atlas and brush-dab atlas are two textures | PX W3 |
| **Self-shadow / bounce / heat spread / paint / big-set proximity** | SA3, SA5, SA21, SA23, K36, GE2 | **one** coarse voxel grid service in `/project1/effectors` (2D-tiled atlas, not Texture3D) | effectors lane E + PX W3 |

Not merged (kept distinct on purpose): SX-11 motion interpolation (needs user answer), 7C-26 VAT (tool), 7C-27 Metavido
(source decoder), TC-06 / TC-40 (arm64 helpers, user input), TC-38 POP->DMX, TC-39 PSN.

## 2. Structure decisions (lean)

| Decision | Yes / no | One-line reason |
|---|---|---|
| **FX_stylise** (= FX7a FX_stylise + FX7c FX_paint + backlog #71) | **YES** | 6+ strong modules (outline/contour, saber, boil, ink/toon, engraving, clean, watercolour, kuwahara) share two real pieces (JFA distance, bilateral/structure-tensor pass); they are image filters used on a different layer from FX_film. |
| **FX_glass** | **YES** | 3 strong items (liquid, rain, frost/reeded/fly-eye) + foil + wet floor share one pre-blurred backdrop input; putting them in FX_film (already 14 modules) would make its bring-home heavier (T-152). |
| **FX_track** | **YES, small** | one blob-tracker source (Blob Track TOP/CHOP on the stored webcam clip) is shared by plexus, HUD and analytics and also feeds `FX_glitch.misc` electrify arcs (TC-03) and effectors `pts`; without the COMP each would duplicate the tracker. Starts with plexus + HUD; analytics later. |
| **CAM_rig** | **NO (no COMP)** | crane + director + view store are a few expressions: `builders/cam_rig_logic.py` (pure Python) used now by PX's Camera page (K24) and BL_splat_render's camera; lift into a COMP only if a third consumer asks. |
| FX_depth25 (FX7c) | NO | the relief-march parallax is one module: GEN_interactive.parallax. |
| FX_paint (FX7c) | NO | = FX_stylise. |
| FSR upscaler (SX-10) | **shared GLSL files, no COMP** | `glsl/fsr_easu.glsl` + `fsr_rcas.glsl`; consumer 1 = GEN_sdf `Upscale` menu (GEN_sdf is 4.81 ms at defaults, OVER), consumer 2 = BL_splat_render / PX (W3); BN_fluid2d later. |
| Voxel grid service | **in effectors, built with its first 2 consumers** | K36 distance field + SA23 paint volume (lane E) are the 2 real users; SA5 / SA3 / SA21 read it later. 2D-tiled rgba16f compute TOP (known-safe class, T-47), no Texture3D / POP buffers (T-124). |
| JFA | **reuse, no new shared file** | FX_stylise includes `gen_sim_vor_jfa.glsl` read-only; GEN_sim untouched. |
| `td_vat_load` tool (7C-26) | YES | Blender integration approved 26 Oct; VAT is how baked sims play at 60 fps. |
| `td_psn` (TC-39), `td_coreml_bridge` (TC-40), flow helper (TC-06) | NO for now | need the user (s6). |

## 3. Ranked list

Score = value for live shows + Ruben Fro coverage, against cost (ms + hours), risk (T-124 / T-152 class) and fit (extends
something live). User-flagged Ruben Fro work ranks first by rule.

### 3a. Top 20

| Rank | Item | Rows | Home | Est. ms | Lane | Why here |
|---|---|---|---|---|---|---|
| 1 | Lights + colour in PX: shared effectors, `light` module (normals, delight, toon/rim), palette everywhere, bloom v2 | K37, L1, L2, SA1, SA2, SA7, CO2-CO5, K33, GL1, GL3 | PX W2-1..3 | +0.3-0.8 | P | the user's "lights must affect the splats" + "change colours"; W1-A/B/D already built |
| 2 | Lines + haze inside PX | G1-G6, H1-H3, H4 preset | PX W2-4 | +1.3-1.8 | P | "green lines", "volumetric haze"; W1-C/D built |
| 3 | Geometry in PX + proxy occluders / shadows | GE1, GE4, SA4 | PX W2-5 | +0.2-0.4 per shadowed light | P | "place geometry ... it should affect the splats"; W1-E recipe exists |
| 4 | FSR 1 upscale (EASU + RCAS) | SX-10 | glsl + GEN_sdf | 0.3-0.5 | C | fixes measured over-budget GEN_sdf; unlocks every raymarch row |
| 5 | Splat depth pass + flares the scan can block | SA13, SA8 | PX W2-6, W2-7 | +1.5-2 (half res) / < 0.1 | P | depth edges, haze occlusion, slab, DOF; believable lights for ~0.1 ms |
| 6 | Distance-field outline / contour echo / neon halo | SX-06, 7C-05 | FX_stylise.outline | 0.5-1.0 | B | top LED look for logos, names (whole words), people |
| 7 | Beat-ripple pool | TC-33 | FX_trans.beatripple | 0.3-0.6 | C | cheapest musical accent; transition + displacer |
| 8 | Fireworks | SX-15, 7C-10 | GEN_pattern.fireworks | 0.8-1.4 | A | finale / drop look nobody built; beat `Hit` |
| 9 | Liquid glass | SX-01, 7C-23 | FX_glass.liquid | 0.3-1.0 | B | the 2025-26 glass look over names / lyrics / crowd |
| 10 | Hydra modulate bank (9 modes) | SX-12 | FX_synth.modulate | 0.15-0.35 | C | VJ classic, chains with vfeedback; tiny |
| 11 | Light-trail ribbons from particles | TC-08 (+TC-13 vortex/strands) | BO_particles via PX_lines | 1-2.5 | G | big-wall neon streaks with no POP risk |
| 12 | Beam fans / laser show | TC-32, 7C-20 | GEN_pattern.beams | 0.5-1.2 | A | concert light vocabulary in 2D |
| 13 | Rigid packet glitch (reassemble on beat) | SA18 | PX W3 `glitch` Packet | ~0 | P | production-proven (Superman); one extension |
| 14 | Wave-equation ripple water + lava-lamp mixing | SX-24, SX-25 | GEN_sim.ripple, .lavalamp | 0.15-0.7 | A | interactive ripples from kicks / person; endless calm mixing |
| 15 | Molten chrome (2D) | TC-23 | GEN_pattern.moltenchrome | 0.4-0.8 | A | hero background, pure TOP maths |
| 16 | Aurora | SX-13, 7C-13 | GEN_sdf.aurora | 1-1.8 at Q0.5 | C | calm high-impact ambient (MIT port exists) |
| 17 | Bokeh parallax drift | SX-22 | GEN_pattern.bokeh | 0.3-0.5 | A | safest always-on backdrop for talk / hold states |
| 18 | Camera page: path / follow / roll / shake + crane + auto director | K24, TC-36 | PX W3 + `cam_rig_logic.py` | ~0 | P | multiplies every 3D look for ~0 ms |
| 19 | Line boil + ink / toon / comic | 7C-01, SX-07 | FX_stylise.boil, .ink | 0.3-0.8 | B | changes how any footage feels; cheap |
| 20 | Voxel grid service + emissive bounce light | SA5 (+K36, SA23 users) | effectors (E) + PX W3 | 0.4-0.8 | E -> P | fire / orbs light the alley (Ruben's ALLEY look, really lit) |

### 3b. Next (21-45, in order)

21 TC-01 blob plexus (FX_track.plexus) - 22 TC-17 4D rotation, **GLSL state-texture route** in GEN_points.polytope4d (no
POP) - 23 7C-09 saber (FX_stylise.saber) - 24 SX-30/7C-31/TC-05 parallax still (GEN_interactive.parallax) - 25 7C-22 holo
foil (FX_glass.foil) - 26 SA6 screen-as-light (effectors kind `light` type `env`) - 27 SX-05 clean / despeckle
(FX_stylise.clean) - 28 SX-27/7C-15 sand (GEN_sim.sand) - 29 7C-02 watercolour (FX_stylise.watercolour) - 30 SX-02/7C-34
rain on glass - 31 SX-31 melt / burn / dissolve transitions + SX-34 blur / warp family (FX_trans) - 32 SA31/TC-37 actor
echoes (PX W3) - 33 TC-24 masked streak lite + TC-25 strips + TC-26 RGB time split (FX_glitch modes) - 34 SX-03 frost /
reeded / fly-eye (FX_glass.frost) - 35 7C-04 engraving (FX_stylise.engrave) - 36 TC-02 tracking HUD (FX_track.hud) - 37
SA23 painted mask volume (effectors) - 38 SX-18 sky + TC-34 ringed planet + TC-35 dreamcore preset (GEN_sdf) - 39
SA19/SA20 dissolve fronts + spiral reveal (PX W3) - 40 7C-26 VAT tool (`td_vat_load`) - 41 SA22 focal slab + SA14/SA15
splat attributes (PX W3) - 42 SA21 heat spread (PX W3, needs grid) - 43 #71 Kuwahara (FX_stylise.kuwahara) - 44 7C-18
hyperspace streaks + 7C-19 mirror ball (GEN_points) - 45 SX-08 pixel-art + SX-09 scalers + TC-27 stitch (FX_retro).

### 3c. Tail (build by need, roughly in this order)

SX-14 ocean, 7C-16 ferrofluid, SX-17 cloud, SX-19 black hole, SX-20 terrain, SX-23 fractal presets (GEN_sdf, all behind
FSR); SX-16 star nest, SX-21 flame overlay, SX-28 shield, SX-29 rooms, 7C-17 synthwave, 7C-29 jigsaw, TC-21 packing,
TC-29 pendulum (GEN_pattern); SX-26 bubbles (GEN_sim); SX-32/33/35 transition families, 7C-06 page flip (FX_trans);
TC-31 cadence, TC-03 electrify points input, 7C-33 hex mosaic (FX_glitch); TC-04 analytics (FX_track); TC-28 strings,
7C-25 Skinner shards (GEN_interactive); 7C-08 light wrap (CV_person_mask); 7C-21 wet floor (FX_glass.floor); 7C-11
confetti, 7C-10 BO fireworks shells, 7C-24 liquid-metal SSF (read yeataro first) (BO_particles); 7C-12 N-body, TC-20
video-to-particles (GEN_points.form source clip); TC-22 fake fluid lite (BN_fluid2d, technique not public); 7C-03 brush
strokes (FX_stylise); 7C-07 PS1 look (FX_retro + MAT probe `noperspective`); 7C-30 sonar grid, SA9 mirror floor, SA11
SH rotation, SA12 covariance follow, SA17 temporal denoise, SA24 accumulation, SA25 rain preset, SA27 copies, SA28
skinning, SA29 bones effectors, SA32 metric depth, SA34 scan-error synthesis, SA35 dab sprite, K19/K28 source `top`, K21
glyph atlas, K22 strands, K26 fisheye / equirect, K27 image source (PX W3); 7C-27 Metavido; TC-38 POP -> DMX
(`dmx_patch` source); SA3 opacity self-shadow (after SA4, user default); SA10 refractive, SA26 jelly (low confidence / L);
K34 data -> sound (only when asked); SX-11 motion interpolation (user input); 7C-32 fur shells; 7C-28 tentacles. POP-
structural items: lane H only (s5).

## 4. Wave 2: PX owner, sequential (lane P, TD b5; starts when W1-C is in main)

One owner for `builders/px*.py`, `px_lines*.py`, `px_haze*.py`, `glsl/px_*.glsl`, `splat_render*` (W1-E files) and
`test/test_px*.py` for the whole of waves 2-3. Each step: scratch-class code first if it introduces a new shader class,
else straight on b5; checkpoint after every verified step; PX comes home **by builder** (T-152), one step per exec.

| Step | Builds | Rows | Depends on | Live checks (expected = the W1 numpy refs) | Est. h |
|---|---|---|---|---|---|
| W2-1 | PX reads the shared `/project1/effectors` packed buffer (`pxe*`); legacy `px_eff` kept until presets ported, then removed in one change | K37 | W1-A | every PX preset recalls with identical output (diff 0) on the shared list; adding / removing an effector: no recompile | 2 |
| W2-2 | `light` colour module: half-lambert / lambert / wrap / no-normal glow, Blinn spec, `relight`, ambient; models menu adds `toon` + `rim`; load pass writes PCA normals (`nrm`, octahedral) + delit colour (`Delight` 0..1) | L1, L2, SA2, SA1, SA7 | W2-1 | `light` on splats vs numpy at 10 probes (1e-4); normals: PCA vs ref on a sphere point set (angle < 2 deg); delight on a baked gradient flattens luminance to the ref; toon steps = N | 4.5 |
| W2-3 | Palette page (W1-B `uPal`): `colour_ramp` palette mode + attribute `luma`, colour sources on `prox_colour`, `prox_burn` fire ramp, `Edgecol`, `Glowcolour`, `Hazecol`, `Flaretint`, lines; drive `chop:<name>` + `Palshift`; swap `px_glow` -> `px_bloom` (two scales, `Bloomtint`, ring halo) | CO2-CO5, K33, GL1, GL3 | W2-2 | `pxPal` in PX = numpy (1e-6); FX_palette_map renders identically (diff 0); bloom white tint = old glow (diff 0, W1-D check); Palshift beat-steps once per beat | 2.5 |
| W2-4 | PX_lines as PX's lines layer (before `trail` / glow), edges on render luma + alpha; FX_haze in the post chain (after `sw_trail`, before grade); presets Neon rings, Edge lines, Floor ribbons, Haze shafts, Fire clouds (H4) | G1-G6, H1-H4 | W1-C in main, W2-3 | W1-C LC numbers again inside PX (ring px radius +-0.5, width constant over depth); haze vs closed-form airlight (< 1 %); off = identical; std 131 k: lines + haze <= +1.8 ms | 3 |
| W2-5 | Geo page on PX (sprite + splat Render TOPs, W1-E recipe), lights from the list; `Proxy` flag per geometry (depth only, not drawn) -> per-light shadow depth (1024^2) read by `light` and the haze march; preset Chrome in scan | GE1, GE4, SA4 | W2-4 | box in front covers splats (2/255), behind hidden (alpha > 0.95), sort inversions <= 0.05 %; proxy box: lit side vs shadow side ratio = ref; haze shaft stops at the proxy | 3.5 |
| W2-6 | Splat expected-depth pass `(alpha z, alpha)` at half res -> lines `edges` depth mode, haze occluder, geo softness, `Dof` slab mode | SA13, SA22 | W2-5 | zbar on a two-plane splat test = ref (1 %); depth edges appear only at the plane step; slab band width = par | 2.5 |
| W2-7 | Flares from the light list: per light screen pos, visibility = 1 - mean(alpha) over a 12-16 tap disc; flare / ghost / ring x vis | SA8 | W2-6 | light half behind an opaque splat block: vis 0.5 +-0.05; fully covered -> 0 | 1 |
| W2-8 | Presets + cost pass: Light sweep, Acid palette, all W2 presets recalled on `truck.splat` (points) + SmileyPinata (splats), capture each; one cost table, others parked | all W2 | W2-7 | lines + haze + light + palette on std 131 k <= +2.5 ms over the KANDA-swipe baseline; real fps recorded | 2 |
| | | | | **wave 2 total** | **~21 h** |

**Wave 3 (same owner, after W2-8; order by rank):** SA18 packet glitch (1.5 h) -> K24 Camera page + crane / director via
`cam_rig_logic.py` (TC-36) (3 h) -> SA16 + K25 velocity / camera blur (2 h) -> SA31 + TC-37 echoes (2.5 h) -> SA19 / SA20
dissolve fronts (1.5 h) -> SA14 / SA15 attributes + SA22 rest (1 h) -> SA5 bounce + SA21 heat spread (read lane E's grid;
3 h) -> K19 / K28 Source + Actormode `top`, K27 image (3 h) -> K21 glyph + SA35 dab atlas (2 h) -> K22 strands preset (0.5
h) -> SA33 `knn` lines source (2 h) -> then the PX tail of s3c. **~22 h** to SA33. K26 fisheye / equirect, SA28 skinning,
SA26 jelly only on request.

## 5. Lanes for everything else

<= 4 live at once: **P on b5, A on b3, B on b4, C on scratch** (round 1). Every lane does its **offline prep first**
(builder, numpy reference where the maths is non-trivial, glslc, offline tests, LIVE CHECKS table in its build doc) while
waiting for a TD; registers with `tools/lane.py`; parks others; checkpoints after each module. When a round-1 lane
finishes, the next lane in the queue takes its TD automatically: **D -> E -> F -> G**. Lane H runs **alone**.

| Lane | TD | Owns (one owner per file / COMP) | Items in order (row ids) | Live checks summary | Est. h |
|---|---|---|---|---|---|
| **P** PX owner | b5 | s4 files | wave 2 (s4) then wave 3 | s4 | ~43 |
| **A** 2D generators | b3 | `gen_pattern*.py` + its glsl, `gen_sim*.py` + glsl, `test/test_gen_pattern*`, `test_gen_sim*`, `docs/builds/gen_pattern.md`, `gen_sim.md` | GEN_pattern: fireworks (SX-15 / 7C-10) pilot -> bokeh (SX-22) -> beams (TC-32 / 7C-20) -> moltenchrome (TC-23) -> caustic (SX-04); GEN_sim: ripple (SX-24) -> lavalamp (SX-25) -> sand (SX-27 / 7C-15); then tail patterns | number checks + one capture each (simple one-pass); fireworks: burst count per `Hit` = 1, palette stops visible; ripple: energy decays at the damping rate (numpy 1e-3); lavalamp density conserved +-1 %; sand mass conserved exactly; each module solo <= 3 ms incl. rack floor | ~19 (top 8 ~14) |
| **B** image FX racks | b4 | new `builders/fx_stylise*.py` + `glsl/fx_stylise_*`, new `fx_glass*.py` + glsl, tests, `docs/builds/fx_stylise.md`, `fx_glass.md` | FX_stylise rack + outline (SX-06 / 7C-05) pilot -> boil (7C-01) -> ink / toon / comic (SX-07) -> saber (7C-09) -> clean (SX-05) -> watercolour (7C-02) -> engrave (7C-04) -> kuwahara (#71); FX_glass: liquid (SX-01 / 7C-23) -> foil (7C-22) -> rain (SX-02 / 7C-34) -> frost (SX-03) -> floor (7C-21) | outline: JFA distance vs numpy brute force on a test matte (max err <= 1 px at half res); Amount 0 = passthrough (diff 0); glass: refraction offset = analytic gradient ref; dispersion 3 taps; stored webcam clip for person looks; premultiplied alpha out (overlay rule) | ~26 |
| **C** upscale, transitions, synth, sdf | scratch | `glsl/fsr_*.glsl` (new), `fx_trans*.py` + `glsl/fx_trans/`, `fx_synth*.py` + glsl, `gen_sdf*.py` + glsl, their tests / docs | FSR (SX-10) + GEN_sdf `Upscale` menu -> FX_trans beatripple (TC-33) -> FX_synth.modulate (SX-12) -> GEN_sdf aurora (SX-13) -> sky (SX-18) -> planet (TC-34) -> dreamcore preset (TC-35) -> FX_trans families SX-31, SX-34 (then SX-32/33/35, 7C-06, 7C-29) -> GEN_sdf tail behind FSR | FSR: EASU of a 0.5x render vs bilinear (edge sharpness up, no ringing beyond RCAS limit), GEN_sdf defaults re-measured (target <= 3 ms at the same look); new FX_trans types join `Compile bank` (one compile, T-154); modulate Amount 0 = passthrough; raymarch modules default Quality 0.35-0.5 | ~24 |
| **D** glitch / retro extensions (round 2) | first free | `fx_glitch_*.py` modules touched, `fx_retro_*.py`, their glsl / tests / docs | FX_glitch: smear `strips` (TC-25), pixelsort `Lite` (TC-24), chroma `Time split` (TC-26), mosaic hex / tri (7C-33), misc electrify Points input (TC-03), timeshuffle cadence (TC-31); FX_retro: pixelart (SX-08), scalers (SX-09, check each libretro header), stitch (TC-27), PS1 (7C-07, MAT probe first) | number checks + capture; time split: channel k = frame t - k*d (Cache ref); FX_glitch comes home by builder (15+ modules) | ~16 |
| **E** effectors service (offline from now, live when a TD frees) | first free | `builders/effectors*.py`, `glsl/eff_*.glsl`, `glsl/px_common.glsl` (packed section only), `test/test_effectors.py`, `docs/builds/effectors.md`, new `builders/cam_rig_logic.py` + test | `cam_rig_logic.py` (offline, used by P's W3 camera step) -> SA6 env light (9 SH coeffs from any TOP) -> voxel grid service (2D-tiled rgba16f, 32^3-128^3) -> K36 / GE2 distance field for > 4 k points + mesh surfaces -> SA23 paint volume -> SA29 bones kind (tail) | SH9 irradiance vs numpy (1e-4); grid scatter of a known point set = ref counts; distance field vs brute force max err < 1 cell; packed header bump keeps W = 10 consumers reading unchanged (W1-A rule); 65 k points cost recorded | ~14 |
| **F** tracking + interactive (round 2) | first free | new `fx_track*.py`, `gen_interactive_*.py` touched, `person_mask.py` (light wrap only), tests / docs | FX_track: blob source + plexus (TC-01, via PX_lines `connect`, no POP) -> HUD (TC-02); GEN_interactive.parallax (SX-30 / 7C-31 / TC-05, depth precomputed per still) -> analytics (TC-04) -> strings (TC-28) -> light wrap (7C-08) -> Skinner shards (7C-25) | stored webcam clip only; blob count = Blob Track CHOP rows; plexus segment count = pairs within radius (ref); parallax: zero sway = input (diff 0), occlusion ordering on a two-layer depth test | ~17 |
| **G** particles + points, GLSL routes only (round 2) | first free | `particles*.py`, `gen_points_*.py` touched, tests / docs | BO_particles `lighttrails` preset (TC-08 via standalone PX_lines on BO state; build PX_lines from its builder, no edit) + `vortex` / `strands` (TC-13) -> GEN_points.polytope4d (TC-17, GLSL state texture, no POP) -> hyperspace (7C-18) -> mirror ball (7C-19) -> form source clip (TC-20) -> confetti (7C-11) -> N-body (7C-12, shared-memory probe first) | 4D rotation in all 6 planes vs numpy (1e-5); trail sample count = PX_lines LC numbers; no POP attribute / buffer changes in this lane (if a step needs one, it moves to H); GEN_points comes home by builder | ~18 |
| **H** POP-structural, **build alone, other TDs idle** (T-124) | scratch, with b3 / b4 / b5 stopped (saved first); main kept quiet | per item, its own builder; design + attribute layouts written offline first | TC-07 POP mesh warp (check `Tex` on Grid POP first) -> TC-14 Ray POP collide -> TC-15 fill mesh (Sprinkle POP) -> TC-30 Ray-POP caustics -> TC-08 Skin-POP tubes (smooth curves; artefact fix only in 33070) -> TC-18 GPU L-system -> TC-19 clipmap terrain (glsladvancedPOP) -> TC-12 Voronoi crack 3D -> TC-11 POP<->TOP RD -> TC-09 line growth (prefer a state-texture rewrite in G if it fits) -> TC-10 branching ("crashes" per its author: last, or never) | one item per window; point caps (<= 20-50 k) set offline; first cook watched with `td_watch`; any Vulkan error = stop, LEARNINGS, add a crash pattern | ~25-30 |
| **T** tools (offline; one scratch check each, queued after H windows) | scratch | `tools/blender_export.py` (VAT part), new `td_vat_load` (`src/` + `td/handlers.py` + PROTOCOL), `pointcloud*.py` (Metavido source), `dmx_patch*.py` (POP source) | VAT exporter + `td_vat_load` (7C-26; EXR 32F row fetch by `gl_VertexID` probe) -> Metavido decoder (7C-27, sample from Keijiro's repo into `media/demo/`) -> TC-38 POP -> DMX via `poptoCHOP` | `npm test` + a targeted live call; VAT frame k positions = Blender export (1e-4); Metavido depth = decode ref | ~10 |

Round plan and wall clock: round 1 (P, A, B, C) ~19-26 h per lane; D / E / F / G take the first free TDs (E can start
its offline part now); H windows are scheduled when a round ends (all side TDs saved and stopped first). Total about
**210-220 lane-hours, ~55-60 h wall clock at 4 live lanes** (estimate). Pilot rule: each new rack's first module (A:
fireworks, B: outline, C: FSR) is the pilot; the rest of the lane starts after its pilot is verified.

Per-lane finish (every lane): bring home by builder in a quiet minute, park, save main, `td_library_export` the COMP,
build doc "Verified live" with cook ms + real fps (others parked), LEARNINGS for every bug, RUBENFRO_COVERAGE status
updated for any G/H/GL/CO/L/GE/K row it closes, STATUS top updated, commit by path.

## 6. Needs the user (each has a default so nothing blocks)

| # | Question | Rows | Default if no answer |
|---|---|---|---|
| U1 | Their own scans / performer capture / venue mesh | K19, K4, GE1, SA4, SA28 | demo `truck.splat`, SmileyPinata, generated boxes as proxies |
| U2 | Logos, typography, palettes they want as presets | G6, K21, CO2, SX-06, 7C-05 | Text TOP of a neutral word (whole words, never cut), W1-B 8 neon/fire + Lospec presets |
| U3 | Stills for the 2.5D parallax; OK to add a `depth_still` kind to `camera_bridge` (Depth Anything V2 Small, Apache-2.0, arm64 helper) | SX-30, 7C-31, TC-05 | precompute depth offline with the existing `camera_bridge` depth path; no new helper kind |
| U4 | Arm64 helpers: Vision optical-flow kind (TC-06), CoreML Syphon bridge (TC-40) | TC-06, TC-40, SX-11 | not built; flow needs stay on block matching (FX6) |
| U5 | Purchases: Patreon files (elekktronaut T75-T80, polyhop line growth, Dan Tapper tentacles / feedback, Dith fake fluid), GSOPs, Alaghast plugins | TC-01, TC-09, TC-10, TC-22 | nothing bought; clean-room from the public descriptions; plugins listed in FUTURE.md (x86_64 build unverified) |
| U6 | Houdini VAT files accepted besides Blender? | 7C-26 | Blender only (installed 5.2.2) |
| U7 | Fireworks / confetti / beat-ripple / packet glitch: auto-fire on kick? | SX-15, TC-33, SA18 | `Hit` input wired to AC_audio kick but `Auto` **off**; operator turns it on (no limiter either way) |
| U8 | Ship CC BY-NC-SA Shadertoy ports in a paid show? | SX-02/04/13/14/15/17/20 | clean-room re-writes only; adopted files logged in each module's SOURCES.md |
| U9 | Stored clips play at 24 or 30 fps on the wall? | SX-11 | motion interpolation not built |
| U10 | PosiStageNet output to the lighting desk | TC-39 | not built (only with the LD's agreement) |
| U11 | FX_venue: continue the stopped lane? (wet floor would fit there) | 7C-21 | wet floor goes to FX_glass.floor; `fx_venue_logic.py` left untouched |
| U12 | Self-shadow from opacity (SA3) waits for proxy shadows (SA4)? | SA3 | yes: SA4 in W2-5, SA3 tail |
| U13 | Live camera instead of the stored 5 s clip for FX_track / FX_stylise / parallax checks | TC-01..04, SX-05/06 | stored clip; demo media from `media/demo/` when a face / crowd / dancer is needed |
| U14 | Shadertoy "top since 2024" pass (403 without an account) | FX7a s5 | skipped |
| U15 | Confirm the structure: FX_stylise, FX_glass, FX_track yes; CAM_rig no | s2 | as decided in s2 |

## 7. Risk notes per class

- **POP-structural** (attribute layouts, compute buffers, sort configs, Grid / Ray / Skin / Trail / Feedback / GLSL
  Advanced POP structure changes): lane H only, other TDs saved and stopped, design offline (T-124; scratch does not
  contain a GPU fault).
- **New shader classes** (FSR, JFA in a new rack, Margolus sand, relief march, VAT vertex fetch): scratch first (lane C
  lives there; others queue a one-exec probe there), compile banks up front (T-154).
- **Script CHOP / clocks:** no absTime reads in quiet CHOP cooks; per-N-frame gates count own cooks (T-143) - applies to
  beat ripple, fireworks `Hit`, cadence, director cuts.
- **Big COMPs** go home by builder one module per exec; never two loads at once; a hung load is retried once in a quiet
  minute, twice = stop and report (T-152 / T-153).
- **Budget:** every new module ships with a `Quality` / resolution par and cooks only when its slot is on; the measured
  rack floor (~0.7-1 ms) counts.
