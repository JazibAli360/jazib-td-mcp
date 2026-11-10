# gen_sim: GEN_sim rack + 5 modules `ca` / `voronoi` / `dla` / `blobs` / `lic` (live in main, 26 Oct 2026, TD 2025.31550)

**Status: live in the main TD (26 Oct, 31550), all 5 modules; results in "Verified live" at the end.** Every claim
that needed TD was a **LIVE CHECK** (table near the end, with the numbers expected). Offline: 70 tests (`python3 -I -m unittest discover -s test -p
'test_gen_sim*.py'`, ~9 s), every compute pass compiles with `glslc` against stubs of TD's compute built-ins (a
syntax and type check, not a TD compile), and numpy references in `builders/gen_sim_logic.py` mirror every pass.

`/project1/lab/GEN_sim`. The simulation-generator COMP from `docs/research/FX0_effects_backlog.md` row GEN_sim
(FX5 G08 / G26 CA lab, G10 Voronoi / JFA, G09 Laplacian growth, G12 blobs, G02 LIC). Lean on purpose (user rule 26
Oct, "dont bloat stuff just for modularity"): the rack is `builders/fx_glitch.py` reused as is, the way
`builders/fx_analog.py` does it, plus a small generator variant.

| File | What |
|---|---|
| `builders/gen_sim.py` | rack variant (background, RGB pars, layout) + the helpers all 5 modules use: Colour page, GLSL loader, compute pass, state, clock, Reset pulses, out_sel |
| `builders/gen_sim_<module>.py` | one module each (template: `docs/builds/fx_glitch.md` "Module template") |
| `builders/glsl/gen_sim_*.glsl` | compute shaders; `gen_sim_common.glsl` (hash, value noise, palette, blend) is put in front of each |
| `builders/gen_sim_logic.py` | rule / Lenia expressions, menus, numpy references, `dump_code` + `check` for live parity |
| `test/test_gen_sim*.py` | rack + one file per module |

## Build / rack edits (td_exec)
```python
ns = dict(globals()); exec(open('<repo>/builders/gen_sim.py').read(), ns)
ns['build']('/project1/lab')                          # rack + 'ca1' on first build; idempotent
ns['add']('/project1/lab/GEN_sim', 'voronoi')          # voronoi1, wired last (zkit panel + presets)
ns['remove']('/project1/lab/GEN_sim', 'voronoi1')      # re-routes first, then safe_destroys its ops
ns['rewire'](op('/project1/lab/GEN_sim'))              # after editing `order` in the slots table
```

## Generator variant of the rack
- **No input needed.** `img_src` = Input `auto` (in1 when wired, else `bg`, a black Constant at Resw x Resh,
  default 1080x1920, static) / `black` / `live` / `test` (the rack's webcam clip). Panic = the background straight out.
- **Each module draws over its slot input** (Colour page `Blend`: replace, over, add, screen, multiply, lighten,
  difference, alpha out) and may also use it: CA / DLA seeds and Inject, stained glass, glass refraction, LIC field.
  Stacking slots = layering generators (e.g. `voronoi` stained glass over `lic` ink).
- **Amount 0 = the slot input untouched**: `out_sel` (Switch) passes `in1`, nothing in the module cooks. Bypass / mix
  / Panic come from the rack unchanged.
- **Colour page** (every module): Palette (Colour A -> B, fire, ice, neon, rainbow, mono white, input), Palette shift,
  Blend, Colour A / B (RGB pars; the rack's `_pars` is wrapped to add RGB).
- **State** (`ca`, `dla`): the state texture's alpha holds an epoch = Resetcount + 1. A Reset pulse, or a change of
  a seed-defining par (RESEED list per module), bumps Resetcount through the `pulses` Parameter Execute DAT; the
  state pass sees the epoch (or size) differ and re-seeds. The first frame seeds from the blank (alpha 0).
- **Clock** (`voronoi`, `blobs`, `lic`): 1x1 in-place compute (`clock`) integrating dt x Speed (capped at 0.1 s per
  cook, same-frame re-cooks keep it), so a Speed change never jumps the motion and a bypass does not either.

## Module `ca` (cellular automata lab; `gen_sim_ca.py`)
`in1` -> `state_fb` (Feedback of `step`) -> `step` (compute, 16x16 groups, npasses = steps this frame) -> `look` ->
`out_sel` -> `out1`. State texel r = cell state, g = glow (1 on a live cell, x Decay per step), b = age, a = epoch.
One shared-memory tile (halo = radius, <= 16) serves every family; Lenia's ring kernel is built once per workgroup.

| Family | Rule |
|---|---|
| Life-like / Generations | `Ruleset` menu (Life, HighLife, Seeds, Day & Night, Coral, Maze, Brian's Brain, Star Wars) or `custom` = the `Rule` string, Golly B/S/C (`B3/S23`, `B2/S/C3`); masks come from a par expression (same lambdas as `gen_sim_logic.parse_rule`) |
| Wireworld | 0 empty, 1 head, 2 tail, 3 wire; wire -> head on 1 or 2 heads. Seed = wire lattice (Wirespacing, gaps by Density, Sparks heads) or input above Threshold |
| Cyclic | States N, Threshold, range (Moore box): a cell takes the next state when enough neighbours have it |
| Larger than Life | radius Ltlr box (<= 16), birth / survive ranges (Bosco = R5 B34-45 S34-58) |
| Lenia | A += dt (2 exp(-(U - mu)^2 / 2 sigma^2) - 1), U = ring kernel exp(4 - 1/(r(1 - r))) / its sum (the sum is a par expression) |

Other pars: Cell px (sim = input / Cell), Steps / frame (fractional: 0.5 = every other frame), Run, Wrap, Seedmode
(noise, blob, input threshold, wire lattice, empty), Density, Threshold, Inject (input draws cells every step),
Mutate (random births per cell per step), Decay, Seed, Reset. Look page: Colormode (state, glow trail, age), Shape
(square, round, smooth), Gap, Agescale. Presets: 1 life glow, 2 brians brain, 3 coral, 4 cyclic spirals, 5 wireworld,
6 bosco ltl, 7 lenia worms.
Offline: glider moves 1 cell diagonally in 4 steps, blinker period 2, block still, Brian's Brain / Wireworld /
cyclic transitions, LtL radius 1 B3-3 S2-3 == Life on a random grid, Lenia on a uniform field = the growth formula,
the 'lenia worms' numbers keep > 10 % cover after 120 steps (Lenia at mu 0.15 / sigma 0.015 needs density 0.5 and
R 10 to survive from noise; R 13 soups died offline; slowly moving worm shapes, no orbium glider seed - open item).

## Module `voronoi` (`gen_sim_voronoi.py`)
`in1` + `clock` -> `seed` (scatter: one invocation per seed, manual dispatch ceil(Count / 64); the output relies on
the GLSL TOP clearing it each cook) -> `jfa` (npasses = ceil(log2(max JFA size)) + Extra; step 2^(Pm-1-i), then step
1) -> `look`; `worley` (analytic, one pass) for the Worley modes; `out_sel` picks, so the unused branch idles.
Modes: cells (palette per id + dark outline), stained glass (slot input sampled at the seed), edges (+ glow), distance
(F1), delaunay (Gabriel subgraph: a seed pair whose midpoint's nearest seed is one of the pair, drawn as segments),
Worley F1 / F2 / edges / cells. Edge distance = distance to the bisector with seeds found in 16 samples around the
pixel (exact inside the band). Sources: random, grid (hex rows + Jitter), input luma (8 rejection tries, luma^Bias).
Wander (cells) + Speed move the seeds (Lissajous, reflected at the frame). Res = JFA size (0.5 = 540x960), Extra
0-2. Presets: 1 stained glass, 2 cracked, 3 honeycomb, 4 delaunay net, 5 membrane (Worley), 6 portrait cells (input).
Offline: JFA+1 == brute-force nearest seed on 100 % of 540x960 texels for the default 400 seeds (JFA+0: 99.996 %).

## Module `dla` (Laplacian growth; `gen_sim_dla.py`)
Dielectric breakdown model, all on the GPU (no random walkers): `touch` (2x1 in place, ONE 32x32 workgroup: strike
detector + phimax + regrow count) -> `field` (Laplace phi, 8 Jacobi iterations per pass by temporal blocking: 32x32
tiles iterate in shared memory, 16x16 cores written; npasses = ceil(Iters / 8), manual dispatch ceil(F / 16)) ->
`grow` (npasses = Steps: an empty cell next to the cluster attaches with p = Growth (phi / (phimax Phiref))^Eta) ->
`look` (age / solid / field bands + mip glow). phi = 0 on the cluster, 1 on the electrode (frame sides by Shape, or a
centre disc for Ring); phimax = the largest frontier phi of the last frame (DBM normalisation). Growth waits for
Warmup Jacobi iterations after a restart (phi starts at 1). A strike that reaches the electrode stops the growth;
Autoregrow starts a new one Hold s later (the regrow count is part of the epoch, all GPU side).
Shapes: centre (frost), bottom line (coral), top point (lightning), ring (inward), input threshold (crystallise),
scatter. Presets: 1 frost, 2 lightning (Eta 4), 3 coral, 4 ring, 5 field bands, 6 crystallise.
Offline: Jacobi -> the exact linear profile (< 2e-3), growth rate = p on a uniform field, high Eta grows only at high
phi, warm-up gate, touch per shape, presets grow branches, not blobs. Tuned in numpy at 135x240 / 68x120: without the
phimax normalisation, or with the field at 1/4 of the cells, growth either froze (frontier phi 0) or flooded; with
8-neighbour growth diagonal cells sit off the 4-neighbour frontier phimax is taken on and the cluster floods (option
removed).

## Module `blobs` (`gen_sim_blobs.py`)
`in1` + `clock` -> `fx` (one pass) -> `out_sel`. Field: metaball F = sum (1 - d^2/S^2)^3 (Wyvill, compact support)
with S = r / sqrt(1 - T^(1/3)), so a lone blob's surface is exactly its Radius at any merge Threshold; or SDF
smooth-min of circles (Softness px). Signed distance -> 1 px anti-aliased edge. Each 16x16 workgroup lists the blobs
reaching its tile (prefix-sum compaction in k order, no atomics; Count <= 1024). Motion: wander, lava (rise / fall),
orbit, drift; Radius, Rvar, Pulse + Pulserate. Style: flat (palette per blob), mercury (dome normal, env bands +
specular), neon outline, contour bands, glass (refracts the slot input; use Blend over). Presets: 1 lava, 2 mercury,
3 neon, 4 bands, 5 glass, 6 pulse cells.

## Module `lic` (line integral convolution ink; `gen_sim_lic.py`)
`in1` + `clock` + `fsel` (Field TOP or in1) -> `field` (Fieldres x input, unit direction + magnitude) -> `fx` (RK2
streamlines both ways, Taps per side x Step px, white noise of Grain px, Hann x (1 + Flow cos(2 pi (s Ripples -
phase))) kernel, phase = module time x Flowspeed) -> `out_sel`. Sources: curl noise (fbm stream function), input edges
(luma gradient rotated 90 deg), input gradient, vortex (+ Spiral), Field TOP (rg, e.g. BN_fluid2d velocity), circuit
(curl snapped to Snap directions). Colour: value (palette), field angle, field speed, input x value. Keep Step <=
Grain (default 1 / 1.5 px): with Step > Grain the streak samples alias (along-streak correlation 0.46 vs > 0.8).
Presets: 1 ink wash, 2 brushed steel, 3 combed picture, 4 circuit, 5 vortex rainbow, 6 fluid ink (Field TOP).

## Lane A modules (27 Oct 2026, BUILD_PLAN_27OCT lane A, TD b3)
Rack additions used by the lane A modules only (the 5 first modules' shaders and pages are unchanged):
`colour_page_pal()` (Palette menu + `shared` = index 7 -> `pxPal(t + Palshift)`), `palette_page()` (Palsource /
Palcustom / Palmode / Palinterp / Palreverse / Palcycle /s), `pal_glsl()` (px_palette.glsl first, gs_pal hook),
`H['palette']` (palmap + pal_callbacks + `pal` Script CHOP -> Arrays `uPal` on the look pass; `PAL_CTL` = count,
absTime x Palcycle, mode, interp), `H['hits']` (Hit pulse + rising edge of Hitchan on Hitchop -> `Hitn` + 1; the
state pass applies hits it has not applied yet, so a hit is never replayed or lost), `full_presets()` (every preset
sets the full state: T-124 (1)) and `preset(inst, slot)` (applies a preset like a zkit Recall).

### Module `ripple` (`gen_sim_ripple.py`; FX7a SX-24)
`in1` -> `state_fb` (Feedback of `step`) -> `step` (compute, npasses = Steps) -> `look` (+ in1) -> `out_sel` -> `out1`.
State texel r = height, g = height one step ago, b = hits applied, a = epoch. Step: h' = Damp (2h - h_prev + c2 (sum
of 4 neighbours - 4h)), c2 = 0.5 Wavespeed^2 (0.5 = the CFL limit = Hugo Elias water). Drops: Rain (drops/s; per step
up to 4 hashed candidates; + Audiogain x the Audiochop channel), hits (Hit / Hitchop kick: random place by hit index,
centre or Hitu / Hitv; Hitamp, Hitsize), Inject (slot input luma above Threshold pushes the water: feed a person mask
or motion edge). Edges wrap / reflect (closed tank) / absorb. Look: refract the slot input (Refract px along the
normal, Bump) + specular (Spec, Shine, Lightangle, Colour B), palette by height (Contrast), shaded. Damp 1 never damps
the mean level (constant rain then sinks the pond: physics, no limiter). Presets: 1 rain on the video, 2 kick pond,
3 storm, 4 ink water, 5 person wake.
Offline (`test/test_gen_sim_ripple.py`): seed flat + hits recorded, one dent per hit and never again, energy x Damp per
step (100-step window means, |log ratio - log Damp| < 1e-3 for Damp 0.99 / 0.995), stable at Wavespeed 1 under heavy
rain, rain count = drops/step, uniforms = shader, palette hook, full-state presets, glslc.

### Module `lavalamp` (`gen_sim_lavalamp.py`; FX7a SX-25, clean-room: lygia's file is Prosperity-licensed, not used)
`in1` -> `state_fb` -> `step` (npasses = Steps; inputs state, in1, mass_fb) -> `avg` (Analyze TOP, per-channel mean)
-> `mass` (1x1 book: target = the seeded mean, current mean, epoch) -> `mass_fb`; `look` (in1, step, mass) ->
`out_sel` -> `out1`. State texel xy velocity (sim px / step), z density (0 light .. 1 heavy), w pressure. Step:
semi-Lagrangian advection (bilinear), one warm-started Jacobi pressure iteration, Boussinesq buoyancy (v.y -=
Buoyancy (rho - target)), Viscosity, closed tank. Heat: bottom Heatzone -> light, top -> heavy (Heatnoise = vnoise
along x: separate plumes) = an endless lava lamp; Relax pulls toward the slot input luma (a logo melts and re-forms);
Conserve (pass 0) shifts every texel by target - mean: semi-Lagrangian advection alone drifts the total by +-10 %
(numpy prototype), with the book the drift is one frame's worth (< 0.7 % at 108 x 192, less at the live 432 x 768).
A seed happens when `mass_fb` has not seen the epoch (first frame, Reset, Seedmode / Seed / Fill change). Looks: wax
(smoothstep at Edge +- Soft -> palette; Glow adds speed), glossy wax (+ highlight from the density gradient), bath
(raw density). Presets: 1 lava lamp, 2 rt fingers, 3 neon lamp, 4 logo melt, 5 oil bath.
Offline (`test/test_gen_sim_lavalamp.py`): seeds, density conserved within 1 % over 200 frames (pure mixing and
heated; without Conserve > 1 %), heavy fluid sinks (centre of mass down > 3 px), mass book, uniforms, full presets.

### Module `sand` (`gen_sim_sand.py`; FX7a SX-27 + FX7c 7C-15)
`in1` -> `state_fb` (rgba8) -> `step` (npasses = Steps) -> `look` (+ in1) -> `out_sel` -> `out1`. Margolus 2x2 blocks,
the cut shifts by (1, 1) every step; each thread computes its block's move (hashes of block + step) and writes its own
cell, so cells only swap: sand / water counts are exact. Materials empty / sand / water / wall (outside = wall).
Before the rules: walls from the slot input (Walls, Threshold: a moving funnel), Pour (top band), hits (Hit / kick:
a disc of Hitmat at a random x, never replayed: b = hits applied mod 256), Drain. Rules: fall, topple (diagonal, a
supported grain), flow (water sideways). State r = material / 3, g = grain shade (moves with the grain), b hits, a
epoch (1..255). Look: sand = palette at the shade, water Colour B at Wateralpha, wall grey, Gap. Seeds empty / pile /
input (bright = sand, luma = colour) / layers. Presets: 1 sand cloud, 2 hourglass pour, 3 beach, 4 person funnel, 5
pixel kicks. Offline (`test/test_gen_sim_sand.py`): mass exact over 120 frames (pile, layers), sand falls and the
floor fills, water levels flat (column spread <= 3), one disc per hit, input walls hold sand, rgba8 round trip.

## Live parity tooling
In TD (td_exec, `# allow-readback`, in an exec AFTER the change, T-74 / T-116 (4)):
```python
L = {}; exec(open('<repo>/builders/gen_sim_logic.py').read(), L)
exec(L['dump_code']('/project1/lab/GEN_sim/ca1', '<repo>/output/gen_sim_check/C2', ['state_fb', 'step', 'in1']))
```
then outside TD: `python3 -I builders/gen_sim_logic.py check ca output/gen_sim_check/C2` (also `vor` with ['seed',
'jfa'], `dla` with ['cluster_fb', 'field_fb', 'field'], `blobs` with ['fx', 'clock'], `lic` with ['field', 'fx',
'clock']). The dump saves numpyArray of each TOP (row 0 = bottom, T-58) + every GLSL TOP's vec uniforms + the custom
pars. TD never runs the numpy reference.

## LIVE CHECKS
Measure with the rack's Input = black (or the test clip paused where a picture is needed), pane OFF the COMP for
costs (T-111 (5)), other lab COMPs parked, project 60 fps target, 3 ms per COMP. Build in b2 first (T-120), then
`td_bring_home`, re-check, park, save.

| # | Check | How | Expected |
|---|---|---|---|
| G1 | Build + compile | `build`, then `add` voronoi / dla / blobs / lic; `td_errors`; each GLSL TOP's info | no errors; no stray `<name>_compute1` / `_info` docked templates; zkit panels build (ca `Rule` is a Str par: check the panel copes) |
| G2 | Generator rack | nothing wired, Input auto: `img_src` index 0, `out1` 1080x1920; Panic on: out1 == bg (diff 0); each slot enabled 0, mix 0 and Amount 0: out == slot input (numpy diff 0, 4 frames later) | all 0 |
| G3 | npasses facts | ca Steps 0.5: `step` totalCooks +1 per frame but the state changes every other frame; no recompile when npasses changes (cook ms flat); dla `field` = npasses + manual dispatch together (untested combination) | state advances 30 times/s; field parity D2 passes |
| C1 | CA seed count | ca1 defaults (Life, Cell 4 -> 270x480 sim, Density 0.3, Seed 1), Run off, pulse Reset | `step` r: **39088** alive cells (exact, uint hash); `look` (Colormode state, Palette mono, Blend replace, Gap 0.1): **625408** lit px (16 per cell) |
| C2 | CA parity | Run on, Steps 1, dump `state_fb`, `step` (+ `in1`) -> `check ca`; repeat for Brian's Brain, Wireworld preset, cyclic, Bosco | `state_mismatch` **0**; from C1, after 1 step **44406** alive, after 10 steps **27801** (if read at an exact step count) |
| C3 | Wireworld seed | preset 5 (Wirespacing 10, Density 0.4, Sparks 0.03, Seed 1), Run off, Reset | **18939** wire cells, **612** heads |
| C4 | Lenia | preset 7, dump after a step -> `check ca` | `max_abs` <= 1e-4 (float32 vs float64); cover stays > 10 % after 10 s |
| C5 | Inject / Mutate / Reset | Inject with the test clip; Mutate 0.002; change Seed | cells follow bright areas; ~0.2 % births per step; Seed change re-seeds at once (Resetcount + 1) |
| V1 | Seed scatter | voronoi1 defaults (Count 400, Res 0.5): count `seed` texels with b > 0 | **398-400** (2 seeds in one texel keep one); the rest exactly 0 (relies on clearoutputs on) |
| V2 | JFA parity | dump `seed`, `jfa` -> `check vor` | `jfa_vs_ref_same` >= 0.9999, `jfa_vs_bruteforce_exact` >= 0.9999 (numpy: 1.0 at Extra 1) |
| V3 | Modes | each Mode; Worley modes: `jfa` / `seed` totalCooks stop | stained glass shows the input per cell; delaunay draws a triangle net; capture one |
| D1 | Warm-up | dla1 centre, Reset: count cluster cells per frame | 1 cell for ~**9** frames (24 + 32 per frame >= 256 Jacobi iterations), then it grows |
| D2 | Field parity | dump `cluster_fb`, `field_fb`, `field` -> `check dla` (not on a reset frame) | `field_max_abs` <= 1e-5 (temporal blocking == plain Jacobi) |
| D3 | phimax + strike | dump `touch` texel 1 vs `dla_phimax(field_fb)`; lightning preset: watch `touch` texel 0 | equal to 1e-6; r -> 1 when a branch reaches the bottom, cluster count flat for Hold s, then b + 1 and a new strike from 1 cell |
| B1 | Blobs coverage | blobs1 defaults, Blend alpha out, Speed 0: dump `fx`, `clock` -> `check blobs` | `agree` >= 0.995 (sampled every 7 px; numpy at t = 0: 28.2 % of the frame covered) |
| B2 | Many blobs | Count 1024, Radius 28 | no compile / shared-memory error (22 KB of 32 KB), cost below |
| L1 | LIC parity | lic1 Palette Colour A -> B with A = black, B = white (NOT mono: Mono white is constant white), Blend replace, Colormode value, Speed 0: dump `field`, `fx`, `clock` -> `check lic` | `median_abs` <= 0.01, `p99_abs` <= 0.1 (numpy with 8-bit filter weights: 0.0 / 0.0) |
| L2 | Field TOP | Source Field TOP, Fieldtop = BN_fluid2d velocity | ink follows the fluid; with no Fieldtop the slot input's rg is used |
| RP1 | ripple build | `add` ripple; td_errors; `pal` 16 samples | no errors / warnings (except a missing AC_audio on a side TD) |
| RP2 | ripple step parity | Rain 4, a few hits, Steps 2: dump `state_fb`, `step`, `in1` -> `check ripple` | `max_abs` <= 1e-4 (float32 vs float64, 2 steps) |
| RP3 | one drop per Hit | Hit pulse x3 (and a Constant CHOP kick 0 -> 1): `Hitn` +1 each; state b = Hitn after the next cook | b = Hitn, never more |
| RP4 | energy decay | Rain 0, Edges wrap, after hits: dump `step` every 60 frames x 3 -> energy ratio / steps | per-step log ratio = log Damp +- 1e-3 (window means) |
| RP5 | looks + passthrough | Look refract over the test clip; height; shaded; Amount 0 / enabled 0 / mix 0 / Panic | capture; diff 0 |
| LV1 | lavalamp build | `add` lavalamp; td_errors; avg 1x1 rgba32float | no errors |
| LV2 | lavalamp step parity | preset 1 running: dump `state_fb`, `step`, `mass_fb`, `in1` -> `check lava` | rho p99 <= 0.01, max <= 0.05 (GPU 8-bit filter weights vs quant 8 in numpy; fronts are steep) |
| LV3 | density conserved | read `mass` (target, mean) every 30 frames for 20 s, presets 1 + 2 | abs(mean / target - 1) <= 1 % |
| LV4 | looks + passthrough | capture wax / glossy; Amount 0 / enabled 0 / mix 0 / Panic | diff 0 |
| P1 | Cost | per module, out1 pulled, 120 frames, median sum cpu+gpu | <= 3 ms each at defaults (estimates: ca life 0.3, lenia R10 ~1-2, voronoi ~1, dla ~1.5 (touch pass is one workgroup: if > 0.5 ms use Fieldscale 0.5), blobs 24 ~0.5, lic 20 taps ~1.5); project 60 fps with one module on |

## Verified live (26 Oct 2026, TD 2025.31550)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Shaders first on the scratch TD (`/project1/gen_sim_lane`, removed after), parity dumps there; then built in the main
TD `/project1/lab/GEN_sim` (rack + ca1 / voronoi1 / dla1 / blobs1 / lic1, one `add` per exec, 4-6 s each), checked,
checkpointed (`output/checkpoints/GEN_sim/GEN_sim_20261026-213034.tox`), saved (JazibTD_home.370.toe), parked. Left
with every module on its preset 1, only ca1 enabled, Input auto.
- **G1** compile: 0 errors / warnings on scratch and main, no stray `_compute1` / `_info` templates, zkit panels for all
  5 (ca's Str `Rule` par is fine; 7 / 6 presets seeded). Two rack fixes found here (commit 70e2ea7): the rack's own
  build lays out before `bg` exists (stage op filter), and passes without look uniforms warned "Uniform 'uLook' is not
  assigned" (common declares them; they now get 0s).
- **G2** (main, Input test clip, numpy max abs diff out1 vs img_src): all 5 Amount 0 -> **0**; Amount 1 + every slot
  enabled 0 -> **0**; mix 0 -> **0**; Panic -> **0**. Control: all 5 on = mean diff 0.178.
- **C1** exact: **39088** alive, look **625408** lit px. **C2** `state_mismatch` **0** for Life, Brian's Brain,
  Wireworld, cyclic (preset 4) and Bosco (preset 6). **C3** exact: **18939** wire, **612** heads. **C4** Lenia max_abs
  **1.2e-6**. **C5** (main) Mutate 0.002 on an empty Life field: 241 / 259 births per step of 129600 (0.19 / 0.20 %);
  Inject (test clip, Threshold 0.6): 96.9 % of bright cells alive vs 1.6 % elsewhere; Reset / Seed / Ruleset changes
  each bump Resetcount (the Parameter Execute runs at frame end: read it in the next call).
- **V1** 400 seed texels, the rest exactly 0. **V2** `jfa_vs_ref_same` **1.0**, `jfa_vs_bruteforce_exact` **1.0**.
  **V3** Worley mode: `jfa` totalCooks frozen while `worley` cooks; stained glass capture
  `output/project1_lab_GEN_sim_out1_2026-10-26T16-29-47-646Z.png` (preset 1 over the test clip).
- **D1** after Reset still 1 cluster cell 14 cooks later (>= 9 expected; growth p is small at first), 10804 cells and
  a strike (touch r = 1) a few hundred cooks later. **D2** `field_max_abs` **8.1e-7**. **D3** touch phimax 0.4906755 ==
  `dla_phimax(field_fb)` exactly.
- **B1** `agree` **1.0** (28.7 % covered at the dumped clock). **B2** Count 1024 Radius 28: no errors.
- **L1** `median_abs` **0.00096**, `p99_abs` **0.0020** (with the A -> B black / white palette).
- **Cost** (main, pane off the COMP, out1 pulled 90-120 frames, median cpu+gpu of the module's TOPs cooked that frame,
  Input black). The GPU was shared with 5 busy TDs (scratch, b2-b5) and 6 other live lanes, so numbers moved up to 2x
  between back-to-back runs (T-121 (4)); indicative: **ca life 1.4-1.9 ms, ca Lenia R10 ~2.3, blobs 1.6-2.6** (in budget);
  **voronoi 5-8** (jfa 3-5 + look 2.3-2.8; Res 0.35: jfa 3.1), **dla 5.5-8** (field 3.6-4.6; Iters 16: field 1.5, all 4),
  **lic 6-11** (fx; Taps 12: 2.5) are over the 3 ms aim at defaults: lower Res / Iters / Taps (pars on their pages).
  Real project rate at the time: ~7-23 frames/s with GEN_sim bypassed (other lanes' load; onFrameStart counter), so
  no fair fps number for this COMP yet.
- Not run: G3 (Steps 0.5 cadence), L2 (Field TOP from BN_fluid2d: that COMP is parked and not ours), D3 lightning
  hold / regrow cycle.

## Verified live, lane A (27 Oct 2026, TD 2025.31550, b3; main after the bring-home)
GEN_sim built fresh on b3 by `build('/project1/lab')` (rack + ca1, 400 ops; b3 had no GEN_sim), modules added there.
- **ripple** (`ripple1`): RP1 td_errors clean (only a b3 warning: no `AC_audio`); RP2 parity with Rain 6, Inject 0.2 over
  the playing test clip, 3 hits, Steps 2: **max_abs 7.8e-6** over 518400 texels (h_rms 5.2), hits_applied 3 = Hitn.
  RP3 one Hit = Hitn + 1 (3 pulses -> 3, 5 more -> 8); a Constant CHOP `kick` 0 -> 1 on Hitchop -> 9 (exactly one).
  RP4 free waves after 5 hits (Rain 0, wrap, Damp 0.99): log-energy slope over 60 samples / 354 steps =
  **-0.010034 per step vs log 0.99 = -0.010050** (diff 1.7e-5). RP5 Amount 0 / enabled 0 / mix 0 / Panic: **0** (test
  clip std 0.23). Cost (pane off, 110 forced pulls): step **0.24** + look **0.21 ms** GPU, CPU 0.23 (estimate
  0.15-0.3 GPU). Capture `output/project1_lab_GEN_sim_ripple1_out1_2026-10-26T22-17-28-081Z.png` (refract over the clip).
- **lavalamp** (`lavalamp1`, sim 432 x 768): LV1 td_errors clean, avg / mass 1x1. LV3 preset 1 (blobs, Heat 0.05) 40
  reads of `mass` over 20 s: target 0.32715, **max abs(mean / target - 1) = 0.68 %** (the one-frame drift the book
  removes next frame; steady 0.12 %). LV2 parity (state_fb, step, mass_fb): **rho p99 8.4e-6, max 1.1e-3, velocity max
  3.6e-3** (numpy with 8-bit filter weights); live mean = ref mean to 1e-8. LV4 Amount 0 / mix 0: **0**. Look fix
  live: the glossy highlight saturated on tiny gradients (stripes in the light fluid) -> smoothstep(0.02, 0.3, abs(grad)).
  Cost (pane off, 110 pulls): step 0.28 + avg 0.12 + mass 0.07 + look 0.20 = **0.66 ms GPU**, CPU 0.45. Capture
  `output/project1_lab_GEN_sim_lavalamp1_out1_2026-10-26T22-24-50-916Z.png`.
- **sand** (`sand1`, sim 540 x 960, rgba8): td_errors clean; parity (state_fb -> step, 2 Margolus steps, preset 1):
  **material_mismatch 0 of 518400**, shade max 3e-8; counts before = after = ref (99774 sand). Mass over 20 reads / 328
  cooks (656 steps): **99774 sand every read** (exact) while the sand's mean row fell 406 -> 92. Amount 0: **0**. Cost:
  step **0.12** + look **0.11 ms** GPU, CPU 0.25. Capture (pour + 3 hits over the test clip)
  `output/project1_lab_GEN_sim_sand1_out1_2026-10-26T22-32-01-654Z.png`. (A scratch-TD probe of the Margolus pass was
  planned per s7 but scratch was hung by another lane; the pass is the CA step's class: built on b3 directly.)

## Perf pass (26 Oct, 2025.31550, b5 -> main; perf lane)
Method: paired A/B in the same frames (a copy of the pass with the other text or format, same inputs and uniforms,
both force-cooked every frame in alternating order, GPU ms, one sample per frame; LEARNINGS T-145). Two copies are
compared when the original's own cost is skewed (the original `dla1/field` reads 1.1-1.7 ms where an identical copy
reads 0.7: its feedback chain cooks with it), A/A check 0.94-1.0. Module at preset 1, Input black.
- **dla `field`: one fetch when the 4x4 grounding samples all land in one sim cell** (field size = sim size, the
  default): the 16 identical fetches per cell per pass were the cost. Same result (exact); **0.68x time (1.5x faster)**.
  D2 after it: `field_max_abs` **6.9e-7** (13133 cluster cells).
- **lic `field` rgba32float -> rgba16float:** the streamline loop's two bilinear field fetches per tap are the cost
  (a precomputed weight table for the 2 cos per tap: 1.03x, not kept; noise from a texture instead of the hash:
  slower). Offline: 16F changes v less than the GPU's 8-bit filter weights already do (median 0, p99 <= filter p99;
  test). **fx 0.78-0.81x time (1.25x faster)**: 4.7-5.9 -> 3.7-5.1 ms at Taps 32 (preset 1). L1 after it:
  median_abs **0.0010**, p99 **0.0072** (32F same minute: 0.00098 / 0.0019; bar 0.01 / 0.1).
- **voronoi:** jfa 1.4 ms (11 passes) + look 0.66 at this load (the 5-8 ms above were under 6 busy TDs + lanes): no
  change.
- Still over 3 ms at defaults: **lic preset 1 (Taps 32)**: 3.5-5 ms fx (RK2 = 2 field fetches x 64 taps x 2 M px;
  3.5 in a quieter minute); cost scales with Taps: Taps 20 (the par default) = 1.9 ms in the same minute.

Brought home: `node tools/bring_home.mjs --comp /project1/lab/GEN_sim --from b5 --lane "perf (b5)"`: ops 1618 = b5,
errors 0, parked, **main saved `JazibTD_home.422.toe`** (b5 `Build5.51.toe`).

## Not done / open
- lic over 3 ms at preset 1 (Taps 32) after the perf pass; ideas left: shared streamlines (FastLIC), Euler steps
  (one fetch, a look change). voronoi / dla measured under budget at the perf pass (see above).
- Lenia has no orbium (glider) seed; the preset is the worm regime that survives from noise.
- No effector / mouse drawing into CA or DLA (Inject from the slot input covers drawing with any TOP).
- No Lloyd relaxation for voronoi (stateless seeds); FX5 G11 low-poly and G25 stipple not built.
- `dla` touch pass scans the whole field in one workgroup: fine at 270x480, watch it at Cell 1-2.

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.742).
