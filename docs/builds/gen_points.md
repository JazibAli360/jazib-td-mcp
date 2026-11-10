# gen_points: GEN_points rack + 8 point-engine modules (live in main, 26 Oct 2026, TD 2025.31550)

`/project1/lab/GEN_points`. FX0 row "GEN_points" (backlog 40, 44, 66, 67); cards FX5 G04 density2d, G03 attractor3d,
G01 streamlines, FX4 G-FORM form (wave 1); FX5 G15 flame, G05 lsystem, G22 graph, G-SPARKLE sparkle (wave 2, FX0 rows
66 / 67). Research + maths: `docs/research/FX7_gen_points_sources.md`. Not built yet: Particular modules (G-PART2).

**Status: live on 2025.31550, 8 modules (built in b3, brought home into main; see "Verified live" and "Wave 2 + cost
pass"). 23 offline tests; every shader compiles with glslc.**

## Design
- **Rack = GEN_pattern's** (`builders/gen_pattern.py` exec'd, not copied): `slots` table, Cross + Switch per slot,
  background (Input auto / black / live / test clip at Resw x Resh), rack Drive (Bpm or Bpm CHOP, beat CHOP, audio
  level CHOP, Resync), Panic, add / remove / rewire, `preset()`, `freeze()` / `unfreeze()`, `read_uniforms()`.
  `builders/gen_points.py` overrides only `module_ns`, `shared_pages`, `_module_network`, `TOKENS`, `NAME`, `MODULES`.
- **One points engine per module** (all four modules use it, so it is shared; no-bloat rule):
  - `state` compute GLSL, rgba32float, side x side (side = ceil(sqrt(Count + 1))), one texel per point; the last
    texel is the clock (last module time, frame counter, epoch). Module GLSL: `pt_seed(i)`, `pt_step(i, s, dt)`; dt =
    change of the module clock (Speed x (1 + Audiospeed x level)), clamped to 0.1 s; dt 0 (Speed 0, freeze) = hold.
    A new epoch (Reset pulse -> Resetcount + 1, or the module's EPOCH pars, e.g. attractor System) re-seeds.
    `state_fb` (Feedback TOP) = last frame; input 1 = the slot input (picture fields, layer map, bright-pixel spawn).
  - `pts` Grid POP side x side points (static) -> `geo` (Select POP) with `mat` (GLSL MAT: vertex reads the state
    texel at `TDPos()` (T-112), module `pt_place()` -> world point + colour, then 2D fit (Zoom / Rotate / Centre /
    Fold copies) or 3D orbit camera (Yaw / Pitch / Orbit / Distance / Fov / Depthfade); 1-px points (Size 1, exact
    counts) or sprites (Size > 1: disc / star glint / square); blend one/one, depth off) -> `render` Render TOP
    rgba32float at the input size x Quality. This is GN_physarum's live-verified scatter-add (T-112). No POP compute
    buffers, attributes or loops (T-124, F11).
  - Render format by `Precision`: half (rgba16float, default, ~2x less bandwidth, sums rel ~4e-4) / float (exact).
  - `look` compute (Persist 0) and `look_acc` (Persist > 0; cost pass 26 Oct): look_acc keeps the trail acc = render +
    Persist x last acc IN PLACE in its colour buffer 1 (`outputaccess readwrite`, `clearoutputs` off, T-151 (1)), so
    the v1 acc pass + acc_fb Feedback + acc_sel are gone. rgba16float out, HDR kept. Tone Soft (1 - exp) / Linear / Log
    density (flame style, Vibrancy mixes per-channel log and hue-preserving log), Exposure (stops), Gamma; `Normalize`
    density = divide by pixels per point (RW x RH x (1 - Persist) / Count, even spread = 1) or off (raw sums x (1 -
    Persist): sprites, sparkle); Glow = 3 mip taps of this frame's render (input filter mipmap ONLY when Glow > 0: the
    mips cost ~1.2 ms a frame otherwise); Beatflash x the beat pulse; blended over the slot input: Replace (Bgcolor +
    points) / Add (default) / Screen / Lighten / Alpha out (premultiplied).
  - `out_sel`: Amount 0 = the input untouched (nothing cooks); else look (Persist 0) or look_acc.
  - Blanks are 2 x 2 constants (a side-sized blank followed in1's size and re-filled on every change).
  - Optional `aux` Script TOP (module `AUX_SCRIPT`, state input 2 = `GP_AUX`): module data built in Python only when
    its pars change (lsystem's segment table). `GP_ST` = the state texture in state and MAT (graph reads node texels),
    `gpTex(j)` = texel of point j, `PSIZE` = per-point sprite scale (pt_place), Sprite `glint` = core + Rays thin rays
    (Rays / Raywidth / Rayangle on Points).
- **Effectors** (shared `/project1/effectors`, page Effectors, **Effon default off**), via `builders/effectors.py`
  helpers (not edited): attractor3d + streamlines use the BO_particles adapter (push / attract / vortex / wake /
  drag / kill / spawn at effectors) in `state`; form uses the points adapter (push / dissolve or reveal per point:
  Trapcode Form's spherical field and more). density2d has none (a map re-converges in a few iterations).
- **Drive:** rack Bpm / beat CHOP / audio; module Speed, Phase, Audiospeed, Audiogain (-> the module's look target),
  Beatevery + Beatgain + Beatdecay (pulse ENV), Seed. No limits anywhere (user rule).

Files: `builders/gen_points.py` (engine + rack overrides + live checks), `builders/gen_points_<module>.py` x 8
(data: pages, presets, uniforms, GLSL COMMON / STEP / PLACE), `builders/gen_points_logic.py` (numpy mirror: seeds,
steps, place, projection, additive count image, tone, compose; reuses px_logic np_* noise and gen_pattern_logic
palette), `test/test_gen_points.py` (17 tests, ~7 s: specs, uniforms declared + expressions compile, glslc of every
shader incl. effector-prefixed state and probe, fake-TD build of each network, mirror maths, every preset renders).

## Modules
| Module | Kind | What | Audio (Audiogain) | Beat | Presets |
|---|---|---|---|---|---|
| density2d | 2D | Clifford / de Jong / Svensson / Bedhead / Tinkerbell, Iterations per frame, Drift LFO, Fold | a b c d nudge | Kick -> params | lace, smoke, starfield, bedhead fold, beat drift |
| attractor3d | 3D | Lorenz / Thomas / Aizawa / Halvorsen / Dadras / Chen / Rossler / Sprott / RF / four-wing, RK4 (auto substeps <= 32), blob or box seeds, Fadein | params x (1 + 5 %) | Kick -> params | thomas silk, aizawa torus, halvorsen petals, lorenz ribbons, dadras beat |
| streamlines | 2D | agents in curl / angle / circuit / picture contours / gradient / vortex / rain fields, RK2, Life, spawn anywhere / edge / centre / bright pixels | (Audiospeed) | via Drive | silk, hair, circuit, vortex, rain |
| form | 3D | box layers / sphere shells / cylinder / plane, fbm or curl displacement, input luma map + colour, Disperse, Twist | displacement x (1 + level) | Kick -> disperse | form grid, sphere shells, curl cloud, picture terrain, twist beat |
| flame | 2D | chaos game, 6 genomes (offline search) x 4 xforms, 16 variations, genome A -> B morph (+ LFO), Xrotate (Electric Sheep), Variation / Varweight added live, Fold symmetry | morph + 0.5 x level | Kick -> morph | ring swirl, loops morph, eye fold, leaf swirl var, hook beat |
| lsystem | 2D | 9 systems + custom (Axiom, Rule1..3, Drawsyms), rewriting + turtle cached in the `aux` Script TOP, points spread evenly along the length, growth by pen order or branch depth (Progress / Growspeed), Sway, Turnjitter, effectors push / dissolve | - | via Drive | plant grow, dragon pen, hilbert, snowflake fold, bush sway |
| graph | 2D | force-directed: Nodes (<= 4096) repel all pairs + springs on a random tree + Extra links, gravity, damping; node glow discs + flowing edge dust drawn from node texels; effectors push nodes | - | Kick -> shake | constellation, dense web, tree, beat shake, sparse stars |
| sparkle | 2D | twinkles that flash (sin^Sharp) and jump each cycle: anywhere / disc / bright input pixels, Drift, glint sprites sized per point, colour palette or input; effectors reveal / push | - | Kick -> flash | gold twinkle, glint on bright, snow glitter, diamond burst, neon dust |

## LIVE CHECKS (build TD b3; ~10 min per module)
Rules: `lane.py add`; one structural change per call + `td_errors`; reads >= 3 frames after a change in another exec
(T-74 / T-116 (4)); start at Count 16384, raise after clean frames (T-124); checkpoint after each module; bring home.
Exec preamble: `ns = dict(globals()); exec(open('<repo>/builders/gen_points.py').read(), ns)`; `C =
'/project1/lab/GEN_points'`; `I = C + '/<module>1'`.
- **S0 build:** `ns['build']('/project1/lab')` -> rack + density2d1, td_errors clean (GLSL compiles in TD: state,
  mat, acc, look), `wires_changed` 9, second build 0. `ns['add'](C, m)` for the others: 7 wires each.
- **A step parity:** preset, run ~2 s, `ns['freeze'](I)`; next exec `ns['probe'](I)`; >= 3 frames later
  `ns['check_step'](I)` -> **within_tol (rel 1e-3) >= 0.99**, median_rel <= 1e-5 (float32 vs float64; chaotic maps
  amplify per iteration, a few fbm-floor flips allowed in streamlines / form). Then `ns['unprobe'](I)`.
- **B render parity:** Persist 0, Size 1, Quality 1, frozen: `ns['check_render'](I)` -> **alpha_sum rel <= 1e-4**,
  rgb sums rel <= 1e-3, **alpha_L1_share <= 0.01** (points on a pixel edge may land one pixel over).
- **C look parity:** Glow 0, frozen: `ns['check_look'](I)` -> within_2_levels >= 0.99.
- **D hold / drive:** frozen -> state identical across two reads; Speed 2 -> clock texel x advances 2 s per s;
  Reset -> clock texel y back to 0 (re-seed).
- **E passthrough:** Amount 0 -> out1 == in1 (diff 0); slot enabled 0 -> rack out1 == img_src.
- **F cost:** pane off the COMP, pull out1 120 frames, sum cpu+gpu of the instance's ops cooked that frame (T-102)
  -> report ms at the default preset Count (aim <= 3 ms; physarum's deposit alone was 2.2 ms at 262k, T-112 (3));
  then one `td_screenshot` of out1 per module.
- **G effectors:** Effon on with `/project1/effectors` present: state compiles, sphere1 pushes (attractor3d /
  streamlines: points within 0.25 of sphere1 drop; form: points near it move outward); Effon off = parity A again.

## Verified live (26 Oct 2026, 2025.31550, build TD b3 -> main)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Method: per module solo in the rack (other slots enabled 0), preset 1 at Count 16384, Persist 0, Glow 0, run ~3 s,
`freeze`, `probe` (one forced step of 1/60 s from state_fb), checks read in later execs (T-74). Effectors: the shared
list built in b3 by `builders/effectors.py build()` (sphere1 at the origin). b3 shared the Mac with 5 other TDs.
| Module | Step parity (rel, 2000 pts) | Render (alpha / rgb sums, px L1) | Look | Effectors (pts within 0.25 / 0.5 of sphere1, off -> on) |
|---|---|---|---|---|
| density2d | max 1.1e-6, all within 1e-3 | exact / exact, 0.79 % | max 0.13 tol units | (none by design) |
| attractor3d | max 1.1e-7 | 15377.748 vs .749 / exact, 0.80 % (15125 of 16384 in view) | exact | 971 -> 0 / 3378 -> 144 (push 4) |
| streamlines | max 6.1e-6; picture contours + bright spawn (test clip): positions max 6.1e-5, angle w (colour only) median 2e-3 rad | exact, 0.85 % | max 0.05 | 1326 -> 390 / 5531 -> 1707 |
| form | max 1.8e-7; picture terrain (luma map + input colour): 8.4e-5 | exact (input colours rel 4.6e-4), 0.67 % (terrain 3.2 %) | exact | 940 -> 0 / 5914 -> 65 (push 0.4) |
- Hold: frozen state identical across reads; Amount 0: out1 == in1 (max diff 0). Drive: Speed 2 -> module time
  +1.76 s per wall s while pulled at 32 fps (Speed CHOP step cap under load, T-124 (2)); Reset -> frame counter 0,
  Resetcount 1. td_errors clean on every build / add (only a layout annotation warning on the rack stage box).
- Fixes found live: look format useinput took the 32F acc (now rgba16float, T-139 (2)); effector force as a world
  velocity (the 0.25 x accel scaling did not move points against the attractor); eff_in refresh (T-139 (1)); acc 16F +
  `acc_sel` bypass; density2d counts 262k -> 131k; attractor Distance 4.5 (5.5 Thomas); form defaults Size 2 sprites +
  Glow 0.6 + neon (gl_PointSize > 1 works, T-139 (4)).
- **Cost** (T-102 sampler, 120 forced out1 pulls, preset 1, solo, back-to-back, 6 busy TDs; noisy x2-3, T-139 (6)):
  density2d 131k Persist 0.9: 10.4 ms median (earlier runs 5.2); attractor3d 131k: 11.1 (5.8 render under load);
  streamlines 65k: 7.4; form 131k Persist 0: 3.6 ms (GPU 1.7). Single-cook split at 131k: Render TOP CPU ~1.8 ms (the
  floor), render GPU ~0.6, acc ~0.6, look ~0.2, state ~0.15 = ~3.4 ms. **3 ms is not reachable with Persist on at
  131k on this loaded Mac**; cost knobs: Count, Quality (render + acc res), Persist 0 (acc bypassed).
- Captures (`output/`): `project1_lab_GEN_points_density2d1_out1_2026-10-26T16-37-52-157Z.png` (Clifford lace),
  `project1_lab_GEN_points_attractor3d1_out1_2026-10-26T16-43-06-761Z.png` (Thomas silk),
  `gen_points_streamlines1_out1_b3.png` (silk), `gen_points_form1_out1_b3_v2.png` (Form grid, Size 2 sprites).
- Brought home: `node tools/bring_home.mjs` -> main `/project1/lab/GEN_points` 1489 ops = b3, errors 0, parked, main
  saved `JazibTD_home.384.toe` (b3 `Build3.64.toe`). Final rack: density2d1 enabled, the other 3 slots enabled 0,
  all at preset 1, Effon off, Input auto, Bpm 120.
- Not verified live: sprite shapes star / square, Fold > 1, density maps other than Clifford, attractor systems other
  than Thomas, real fps of the main TD with GEN_points on (machine load), audio / beat CHOP drive (rack code = GEN_pattern's, verified there).

## Wave 2 + cost pass (26 Oct 2026, 2025.31550, build TD b3 -> main)
Same method as above (solo, Count 16384, Persist 0, Glow 0, Size 1, Quality 1, Precision float, frozen, probe).
| Module | Step parity (rel) | Render (alpha / rgb sums, px L1) | Look | Effectors (pts within 0.25 / 0.5 of sphere1, off -> on) |
|---|---|---|---|---|
| flame (ring swirl) | max 5.5e-4, median 2e-7, all within 1e-3 | exact / exact, 0.87 % | max 0.10 tol units | (none by design) |
| lsystem (plant, depth growth, Progress 0.8) | max 3.1e-6 | exact / exact, 0.66 %; aux table = numpy table (max diff 0) | max 0.05 | hilbert, push 0.4: 2735 -> 0 / 10908 -> 445 |
| graph (constellation, 384 nodes) | nodes max 2.9e-8 (all 384) | exact / exact, 0.69 % | max 0.05 | push 4: 99 -> 0 / 287 -> 18 nodes |
| sparkle (gold twinkle; glint on bright with the test clip) | max 1.0e-3 (one cycle-boundary flip), 0.9995 within 1e-3; bright: 5.8e-8 | exact / exact, 0.90 %; input colours rel 3e-5 | max 0.10 | snow glitter, push 0.4: 868 -> 0 / 6156 -> 229 |
| density2d / attractor3d / streamlines / form (re-check on the new engine) | max 8.8e-7 / 1.2e-7 / 3.1e-8 / 1.8e-7 | exact, 0.63-0.88 % | max <= 0.10 | - |
- Half render (Precision half, form): sums rel 3.4e-4..3.7e-4, px L1 0.91 %. Trail: Persist 0.5 frozen -> acc / render
  1.998 (16F), unlit acc 0. Captures (`output/`): `project1_lab_GEN_points_{flame1,lsystem1,graph1,sparkle1}_out1_2026-10-26T18-0*.png`.
- **Cost** (T-102 sampler, cpu + gpu of the instance's ops, median of 120 forced pulls, preset 1 at the default Count,
  6 TDs busy, x2 swings):
  - Before (v1, start of the lane): density2d 131k 10.1 ms, attractor3d 131k 8.3, streamlines 65k 7.5, form 131k 6.0.
  - v1 vs v2 in the SAME frames (v1 rebuilt from git 7918a5b in a temp COMP, both slots pulled together, old v1
    counts): density2d 8.46 -> 7.22 and 5.04 -> 5.27 ms (GPU 3.65 -> 2.54, 2.07 -> 1.41); streamlines 5.63 -> 3.53 and
    10.88 -> 11.57. Sequential same-minute rounds were inside the noise (+-2 ms).
  - After (v2 defaults, one run back to back): density2d 65k 4.28 (2.2-3.1 after the look ops were recreated, T-151
    (2)), attractor3d 65k 5.35 (4.06 recreated), streamlines 32k 4.62 (4.06 recreated), form 65k 3.96, flame 65k
    2.98, lsystem 65k 2.70, graph 384 nodes / 65k 3.33, sparkle 3000 glints 2.90. Split: render CPU 1.2-1.7 ms (the
    floor) + render GPU 0.3-0.9, look / look_acc 0.25-0.35 (fast state), state 0.1-0.5 (graph's all-pairs 0.3).
  - What changed: look_acc in-place trails (no acc pass + feedback), mips only for Glow, 16F render, 2 x 2 blanks,
    lower default counts (density2d / attractor3d / form 65536, streamlines 32768; Count is still the user's par up to
    1M, Precision float for exact sums). Count changes cost a 160-280 ms Grid POP regen frame (T-151 (4)).
- **Brought home by BUILDER, not tox:** the tox bring-home (2826 ops) froze main > 180 s and the watchdog killed it
  (T-152 / T-153; main recovered on the wave-1 rack). Then in main, one exec per module (~8-13 s each, frames between):
  `_instance` x 4 (rebuild + panel), `add` x 4, presets, layout -> 2826 ops = b3, each module solo: state finite, render
  alpha sums > 0 (density2d 65536 = every point), td_errors 0; parked; main saved `JazibTD_home.436.toe`.
- b3 rack at the end: 8 slots, density2d1 enabled, the rest enabled 0, all at preset 1, Effon off, Input auto, zkit
  panels rebuilt with the new pars and built-in preset rows refreshed (`_refresh_presets`).
- Not verified live: graph / lsystem audio drive, flame Variation weights other than swirl, lsystem custom rules,
  sprite glint parity (sprites are not counted by check_render), real fps of main with GEN_points on.

## Render cost (27 Oct 2026, b3 -> main; docs/builds/RENDER_COST.md, T-198)
- The render floor is the Render TOP op itself (a no-geometry Render TOP = 70-85 % of a 65k render; GEN_points' render
  measured no dearer than a bare one in the same frames). At GEN_points' counts (32k-131k) a compute raster loses
  (crossover ~8k), so the render stays.
- **Fixed:** with the network pane on the rack, every slot's `<slot>_mix` viewer pulled its module, so all 12 modules
  cooked (12 renders, 68-70 ms per frame, b3 12.5 fps). `out_sel` now also goes to 0 (in1) when the slot is off
  (`OUT_SEL_E`: enabled 0 or mix 0): 8.5-11.2 ms, 1 render, 27-43 fps. Parity unchanged (step 4.7e-7, sums exact,
  look in tol). In main (`JazibTD_home.722.toe`).

## Not done / open
- Particular modules (layer emitter, aux, life curves).
- ~3 ms per module only reached by the light modules under load (flame / lsystem / sparkle ~2.7-3.0 ms); the Render
  TOP CPU floor (1.3-2.2 ms on this Mac) leaves ~1 ms for everything else. One shared Render TOP for all slots is
  not possible with this rack: every slot tones and blends over the slot before it (only enabled slots cook anyway).
- look_acc instance-dependent GPU cost (T-151 (2)), unexplained.
- Streamlines are dots per frame (trails come from Persist); no line-segment drawing.
- Sprite sizes > 1 rely on gl_PointSize in a TD GLSL MAT (first live use here).

## Lane G (27 Oct 2026, TD 2025.31550, build TD b3): polytope4d, hyperspace, mirrorball, form clip, nbody
GLSL state-texture routes only (no POP attributes / buffers, T-124). Every module = the same points engine above.

### polytope4d (FX7b TC-17, `builders/gen_points_polytope4d.py`)
4D shapes as dust: the regular polytopes 5-cell / tesseract / 16-cell / 24-cell / 600-cell / 120-cell (vertices +
shortest-distance edges in numpy, circumradius 1: `gen_points_logic.p4_*`, uploaded by the `aux` Script TOP only when
Shape changes: texel 0 = (E, V), texels 1 + 2e / 2 + 2e = the edge ends) or the analytic Clifford torus (Torusratio),
Hopf fibration (Fibers great circles over Hopfrings latitude rings: linked rings under stereographic projection) and
the glome (uniform on S3). Rotation in the six planes in the fixed order XY XZ XW YZ YW ZW (angle Rxx + spin Sxx x
module time x (1 + level); beat Kick adds to XW and YW), then 4D -> 3D: perspective from w = Wdist (w = 0 keeps scale
1), stereographic from the pole w = 1, orthographic, or **slice** (only |w - Wslice| < Slicewidth: the 3D cross-section
that morphs as the shape turns), x Worldsize, then the engine's 3D orbit camera. Dust flows along edges / circles
(Flow), Edgejitter thickens it in 4D, Wfade dims the far side in w; colour by w / element / along / random (palette).
Stateless (pure function of index + module time). Effectors push / dissolve the projected dust (PXE_POINTS). TC-17
suggested Math Combine POP; this is the state-texture route of the plan (s3b row 22).
Presets: tesseract turn, 24-cell slow, hopf links, clifford breathe, 120-cell slice (beat Kick).
Offline: 26 tests (`LaneG`: the six planes = an independent product of Givens rotations to 1e-12, orthonormal, each
plane moves only its two axes; polytope V / E counts 5/10 16/32 8/24 24/96 120/720 600/1200, equal edges, equal
degree; projections; torus / hopf / glome on S3; a Hopf fiber is a great circle), glslc of state / probe / +effectors /
vertex.

| # | LIVE CHECK (b3) | Expected |
|---|---|---|
| P1 | `add(C, 'polytope4d')`, td_errors | 7 wires, state / mat / look / aux compile; aux = `p4_table(Shape)` (max diff 0) |
| P2 | per preset: freeze, probe, `check_step` | within_tol (rel 1e-3) >= 0.99, max_rel <= 1e-4 (rotation + projection vs numpy, all 6 planes spinning) |
| P3 | `check_render`, `check_look` (Persist 0, Glow 0, Size 1) | alpha sums rel <= 1e-4, L1 share <= 0.01; look within 2 levels >= 0.99 |
| P4 | Amount 0; Speed 0 | out1 == in1 (diff 0); state identical across two reads |
| P5 | cost at the preset Count (pane off, others parked) | record; aim <= 3 ms |

**polytope4d verified live (27 Oct, 2025.31550, b3, solo in the rack, load avg 30-44):** `add` = 7 wires, td_errors 0;
aux table = `p4_table('120cell')` (3 x 1024 texels, max diff 0). Step parity (freeze t = 1, probe, 2000 points, all 6
planes spinning): tesseract max_rel 1.6e-7, 24-cell 5.5e-7, hopf 1.3e-5, clifford 3.1e-6, 120-cell slice 1.6e-7
(median 1e-7, within 1e-3 = 1.0 each). Render (tesseract, Precision float): alpha / rgb sums exact (rel 0), px L1 0.86 %
(half: sums rel 1.6e-3, dense edges overflow 16F precision; use float for exact counts). Look: max 0.05 tol units,
within 1.0. Amount 0: out1 == in1 (diff 0). Cost (median of 120 pulls, pane off): tesseract 65k 3.7 ms (render CPU 1.8 =
the floor, state 0.34, look 0.55); 120-cell slice 131k 4.4 ms. Captures `output/laneG_p4_sheet.jpg` (5 presets),
`laneG_p4b_sheet.jpg` (tuned exposure: tesseract, 120-cell slice = pentagon cross-sections). Live fix: `read_uniforms`
in gen_points.py reads array blocks only when the CHOP has r g b pos (the rack version, extended for palettes by lane A,
tripped on the effector buffer arrays of a GEN_points state: TypeError in check_step).

### hyperspace (FX7c card 18, `builders/gen_points_hyperspace.py`)
Star streaks. Each star = Samples points spread along its streak, evenly in screen space (uniform in 1/z between the
head and a tail Stretch seconds of travel behind), re-scattered every frame (Jitter) so Persist / the eye joins them.
Stateless: head depth = Far - ((rnd x L + Warp x module time) mod L), each pass re-rolls the star's place (Field: square
field / tunnel wall ring with Inner / disc, Fieldsize); the jump = ramp the Drive Speed (the module clock integrates it:
no jump in position) and the streak length follows the live speed (Warp x Speed x (1 + Audiospeed x level)) x Stretch x
(1 + Kick x beat pulse). Brightness: tail fade (power), fade in from far, nearer brighter. Colour by depth / star /
speed (the palette shifts with the jump). 2D view page: Rotate deg/s = roll, Centre = vanishing point. Presets: cruise,
jump, tunnel, beat streaks, snowfield dots. Offline tests: a star's samples lie on one ray from the centre, head
outermost, evenly spaced; Stretch 0 = dots; heads move outward over a frame.

### mirrorball (FX7c card 19, `builders/gen_points_mirrorball.py`)
Light spots of a turning mirror ball on the wall. Facets = Fibonacci normals (Count / Lights), spun about y (Spin)
then tilted (Tilt); lights j = 1..4 (Elevation, Azimuth, fanned by Lightspread); a facet facing light j reflects it
(r = 2 (n . L) n - L) to the wall plane z = -Walldist (x Wallscale to the screen); spot sprite size Spotsize x
|1 / r.z|^Elongate (grazing spots grow) x Size px (engine Sprite: soft disc / glint), brightness = facing x twinkle
(per facet, Twinklehz) x fade to the wall edge, beat Kick flashes + grows the spots. Colour by light / facet / position.
Presets: disco, white club (glints), four colours, beat flash, slow glints. Offline tests: every visible spot obeys
angle in = angle out and lies in the plane of n and L; extreme light angles stay finite.

| # | LIVE CHECK (b3, hyperspace + mirrorball) | Expected |
|---|---|---|
| H1 / M1 | `add`, td_errors | 7 wires, compile clean |
| H2 / M2 | freeze, probe, `check_step` (preset 1..5) | within_tol >= 0.99 |
| H3 / M3 | `check_render` (Size 1, Persist 0, Precision float), `check_look` | sums rel <= 1e-4, L1 <= 0.01; look within 1.0 |
| H4 / M4 | Amount 0 | out1 == in1 |
| H5 / M5 | cost per preset 1, capture | record ms |

**hyperspace + mirrorball verified live (27 Oct, 2025.31550, b3, solo, load avg ~30-40):** `add` 7 wires each,
td_errors 0. Step parity, presets 1-5: hyperspace max_rel 3.5e-6..1.0e-5, within 1e-3 = 1.0 (w 0.9995-1.0);
mirrorball (after the off-wall fix) max_rel 6.9e-4..1.2e-3, within 0.999-1.0 (w 0.981-0.995: packKA a quantisation at
1/1023 near rounding edges). First mirrorball run: within 0.978 because grazing reflections landed 13-500 screen units
away with float32 noise (|r.z| ~ 1e-3 amplifies the GPU sin / cos error); off-wall spots (faded to 0 or |w| > 64) now
store 0 (same in the mirror). Render (Size 1, Precision float): hyperspace sums exact (rel 0), L1 0.74 %; mirrorball
with Spotsize 0.5 / Elongate 0 (1-px spots) exact, L1 0.07 % (with real sprites the 1-px count does not apply). Look:
within 1.0 both. Amount 0: out1 == in1 (diff 0) both. Cost (median of 120 pulls): hyperspace cruise 32k 4.8 ms, jump
65k 5.0 (render CPU 1.7-1.8 = the floor, look_acc 1.4 with Persist); mirrorball disco 4.9, white club 5.0 (render CPU
2.2-2.4 with sprites). Capture `output/laneG_hs_t1_*_blk.jpg` (jump), `laneG_mb_t1_*_blk.jpg` (disco spots). Presets
retuned live: hyperspace Exposure 3 (+ Persist 0.3; jump 3.5 / 0.5), mirrorball Exposure 2.5, Spotsize 2, Glow 0.8.

### form: Shape clip + Rise (FX7b TC-20 video to particles, lane G)
`form` gets Shape **clip** (a plane grid in the slot input's aspect: Sizey high, width = Sizey x input aspect) and the
Rise group: bright input pixels (smoothstep from Risethreshold to 1 of the luma) send their point toward the camera
along the normal by up to Rise world units, cycling at Risespeed x (0.5..1.5 per point), spreading by a curl field
(Risecurl) as they go and fading out at the top (1 - phase^4); dark pixels stay on the plane. Persist draws the
trails, Colorby input keeps the clip's colours. Rise 0 = the old form exactly (all earlier presets unchanged). Preset 6
"video particles" (set the rack Input to the test clip or wire a clip). Offline test: plane width = Sizey x aspect, dark
half stays at z = 0, bright half rises (mean > 0.3), fades, Rise 0 = flat.
| # | LIVE CHECK (b3) | Expected |
|---|---|---|
| F1 | `_instance(form1)` rebuild; preset 6 with the rack Input = test clip; td_errors | clean |
| F2 | freeze, probe, `check_step` (in1 = the clip frame) | within_tol >= 0.99 |
| F3 | presets 1-5 again (Rise 0) | parity as before |
| F4 | cost preset 6, capture | record ms |
**form clip verified live (27 Oct, 2025.31550, b3):** `_instance(form1)` rebuild clean; preset 6 on the rack's test clip
(Input test): step parity max_rel 7.5e-4 (luma of the 8-bit clip sampled bilinear; within 1e-3 = 1.0, w 0.9965);
preset 1 after the change: max_rel 2.9e-7 (unchanged path). Cost preset 6 (131k, Persist 0.6, Glow 0.3, Blend replace):
4.4 ms (render CPU 1.7 floor). Capture `output/laneG_form_clip3_*_blk.jpg` (the clip dissolving into rising dust).
Preset 6 retuned live: Blend replace (only the particle version shows), Exposure -1. Note: `freeze()` pauses the rack's
test clip and stores the rack state; after the checks set `test_clip.par.play` back on (unfreeze restores only the
instance it was called for).
**Correction (same day):** the first form-clip check above ran with Shape = plane: instances built before the Shape
menu grew kept the old 4-entry menu (the rack `_pars` skips existing pars), so preset 6's index 4 landed on 'plane'
(main had the same). gen_points.py now wraps the rack `_pars` and extends grown menus (value kept). Re-checked on b3
with Shape = clip: step parity max_rel 8.7e-4 (within 1.0, w 0.9965), render (float, Persist 0, Glow 0) alpha sum exact,
rgb rel 1.9e-4 (input colours), px L1 0.81 %; capture `output/laneG_form_clip4_*_blk.jpg`. LEARNINGS T-190.

### nbody (FX7c card 12, `builders/gen_points_nbody.py`)
Galaxies. The first Bodies texels (<= 4096) are bodies (x, z, vx, vz in the disc plane): Galaxies cores (Coremass) then
exponential discs (scale Discradius, Discmass) on circular orbits (v^2 = G M(<r) r^2 / (r^2 + soft^2)^1.5, core + the
enclosed disc mass); with 2 galaxies they start Separation apart along z (vertical on the portrait screen after the
camera pitch), offset by Impact along x, falling in at Approach, the second co- or counter-rotating (Spin2): tidal
tails, bridges, a merger. All pairs with Plummer softening, **shared-memory tiles of 64 bodies** (each workgroup loads
a tile, barrier, 64 interactions per thread, barrier; the tile loop bound is uniform per workgroup and star-only
workgroups skip it, so the barriers stay in uniform control flow), symplectic Euler with step Timescale x module dt.
The module has its own state `main` (`STATE_MAIN` hook in the engine: same clock / reset / probe logic as the shared
one, no early return before the barriers). Points past Bodies are stateless stars drawn in the MAT around a random
disc body (Starspread, Thickness, Stargain): 131k-262k points on 2k-4k bodies. Log tone (Tonemap 2) by default.
Reset = the collision trigger (re-seed). Colour by speed / galaxy / radius / random.
Offline tests: total momentum kept to 1e-9 over 30 steps (pair forces cancel), stars not simulated, a single core's
disc keeps its radii (median change < 5 % over 60 steps), main has no return before the barriers, 2 barriers.
| # | LIVE CHECK (b3) | Expected |
|---|---|---|
| N1 | probe: add, Bodies 256, Count 16384; td_errors; then Bodies 2048 / Count 131072 | compiles (shared memory + barrier on 31550), no Vulkan error |
| N2 | freeze, probe, `check_step` (preset 1, 2) | bodies within_tol >= 0.99 (float32 tiles vs float64 brute force) |
| N3 | Amount 0; cost presets 1 and 4 (4096 bodies), capture | passthrough 0; record ms |
**nbody verified live (27 Oct, 2025.31550, b3):** shared memory + barrier compute compiled and ran on 31550 (first
cook at 256 bodies / 16k points, then 2048 / 131k and 4096 / 262k; no Vulkan error, td_errors 0). Body parity (all
bodies, probe step vs the float64 brute force): 2048 bodies max_rel 5.0e-7, 4096 bodies (Coresoft) 3.7e-7, within 1e-3
= 1.0; stars stay 0 in the state. Amount 0: out1 == in1 (diff 0). Cost (median of 120 pulls): collision 2048 bodies /
131k points 5.1 ms, dense 4096 / 262k 5.4 ms; the tiled all-pairs pass itself is only **0.22 ms GPU at 2048 and
0.33 ms at 4096 bodies** (16.7 M interactions); the floor is the Render TOP (CPU 2.2-2.4 ms with 131k-262k points).
Live fix: the first version (one softening for every pair) let the two heavy cores slingshot through each other
(softening 0.05) and fly apart at |v| 3-4 (symplectic Euler gains energy in close passes): added `Coresoft` (extra
softening for any pair with a core, symmetric so momentum is kept; disc orbits use it too) and Timescale 0.3: the
galaxies now approach, throw arcs and merge (captures `output/laneG_nb5_sheet.jpg`, `laneG_nb_counter_*_blk.jpg`).
Note: `check_step` samples random points, mostly stars (state 0) for nbody: use the all-bodies comparison above.

**Lane G in main (27 Oct 2026, 2025.31550):** brought home BY BUILDER (no tox load, T-179): `add` polytope4d /
hyperspace / mirrorball (main .666), then `add` nbody + `_instance(form1)` (menu fix, .684); each new module solo in
main: state finite, render alpha > 0, td_errors 0 (polytope4d 49.6k, hyperspace 4.8k, mirrorball 11.8k, form clip 69k,
nbody bodies median radius 0.36); rack restored (density2d1 enabled, the rest 0), parked, saved
`JazibTD_home.684.toe`. Main GEN_points 4171 ops, 13 modules. Library `library/GEN_points/` 0.2.0.
