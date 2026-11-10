# RENDER_COST: what a Render TOP costs on 31550 under Rosetta, and the recipe (27 Oct 2026, b3)

Render-cost lane, build TD **b3**, TD **2025.31550** (Rosetta, M1 Max). LEARNINGS **T-198**. Consumers that hit the
"Render TOP floor": PX_pointfx (px.md), PX_lines (px_lines.md), BO_particles (particles.md), GEN_points
(gen_points.md), FX_track plexus (fx_track.md), FX_synth ruttetra (fx_synth.md).

## Method

- A throwaway bench COMP `/project1/rc_bench` on b3 (deleted at the end): one baseCOMP per variant (Grid POP points
  or 2-point lines -> Select POP in a Geometry COMP -> GLSL MAT reading a side x side rgba32f state texture with
  `texelFetch`, additive one/one, depth off, like GEN_points) -> Render TOP 1080x1920 16F aa1.
- **Paired, same frames (T-145):** a `run(..., delayFrames=k)` tick force-cooks every variant of a batch once per frame
  in rotated order; per variant: `wall` = `time.perf_counter()` around `cook(force=True)` (= main-thread cost,
  includes the MAT cook and its expressions), `cpu` / `gpu` = cook times of the TOPs that cooked. Ratio = median of
  per-frame `wall(variant) / wall(base)`. A/A (same variant twice) gave **0.92-1.19**, so only ratios outside
  ~0.8-1.25 count. 60-90 frames per batch, first 10 dropped.
- **Light sampler** after the T-194 incident (below): one variant + its base per batch at 256x256 (the CPU side does not
  depend on resolution, measured), full res only for the raster comparison.
- Machine: load average 18-66 from macOS processes and the other TDs; absolute ms move 3x with load (the same bare
  Render TOP measured 0.31 ms CPU in one minute and 1.0-1.2 in another), the ratios do not.

## What drives the Render TOP CPU (paired ratios vs a 65k-point render)

| Factor | Result (wall ratio, 2-3 runs) | Verdict |
|---|---|---|
| Render TOP itself, **no geometry** | 0.66 / 0.81 / 0.84 / 0.94 | **the floor: ~70-85 % of a 65k-point render is the Render TOP doing nothing** |
| Geometry render flag off | 0.54 / 0.73 | same floor |
| Constant TOP / GLSL compute TOP / GLSL pixel TOP (1080x1920) | 0.07 / 0.09-0.11 / 0.11 (CPU 0.07 / 0.10-0.12 / 0.14 ms vs render 1.1-1.3) | **a GLSL TOP costs ~1/10 of a Render TOP on the CPU** |
| Point count 4 / 65k / 262k | 1.07 / 1.0 / 1.05 (CPU); GPU 0.21 / 0.20 / 0.43 | no CPU effect |
| Resolution 256x256 vs 1080x1920 | 1.06, 1.51, 1.02, 1.00 | no consistent effect |
| Format 32F, depth float32, dither off, multicamerahint off, aa4 | 1.15 / 1.17 / 1.24 / 1.05 / 1.07 | noise |
| A light in Lights, camera with an absTime expression | 1.11, 0.99 / 1.05, 0.89 | noise |
| No MAT (default) / Constant MAT | 1.58, 0.82, 0.96 / 1.07 | noise |
| Instancing (16 instances), SOP particles (16) | 1.01 / 1.10 | noise (tested small only, see T-194) |
| 2 / 4 Geometry COMPs in one Render TOP | 1.15 / 1.09 | **+0.05-0.15 ms per extra geo** |
| **Render Pass TOP after it** | **1.83 / 2.17 / 1.92** | **a second full Render TOP cost** |
| Downstream TOP consumer | 1.20 / 1.24 / 1.34 | just the consumer's own cook |
| **48 MAT uniform expressions that depend on time** (each reads absTime) | **1.49 / 1.50 (+0.17-0.19 ms)** | **~4 us each per frame** |
| 48 Python expressions NOT time-dependent / 48 plain `parent().par.X` refs (MAT cooking every frame) | 0.96-1.02 / 1.02-1.14 | cached: free |
| GEN_points density2d1's real render vs the bare bench render, same frames | 0.72 (0.73 vs 1.02 ms CPU) | GEN_points adds nothing; the floor is the op |

**Cook triggers (the big one):** a visible node viewer pulls its input. GEN_points' rack keeps a `<slot>_mix` Cross
TOP per slot with its viewer on (user rule: viewers on); with the network pane on the rack, every mix viewer pulled
its module, so **all 12 modules cooked every frame** (12 Render TOPs + states + looks) while only 1 slot was enabled:
**68-70 ms per frame (excl. the test clip), b3 at 12.5 real fps**. Module COMP viewers off: no change; mix viewers
off: only the enabled module cooked. The rack Switch bypassing the slot does not stop a viewer pull.

## Compute rasteriser vs Render TOP (1080x1920, 16F, paired, ms CPU + GPU)

Tile-binned, brute force: one workgroup per 32x32 tile (256 threads) walks all points / segments. Points accumulate in
**shared-memory uint atomics** (integer atomics are core GLSL; TD has no uint TOP formats and macOS no float atomics),
fixed point 1/4096, written with `TDImageStoreOutput`. Lines: each 256-segment batch is culled to the tile into a
shared list (shared atomic counter), then every pixel sums `max(0, 1 - distance)` coverage (gather, no output atomics).
`autodispatchsize` off, dispatch = ceil(W / 32) x ceil(H / 32). One pass, no extra prep pass.

| Count | points: Render TOP | points: compute | lines: Render TOP | lines: compute |
|---|---|---|---|---|
| 1k | - | - | 1.18 + 0.25 | **0.19 + 0.31** |
| 4k | 1.10 + 0.26 | **0.19 + 0.56** | 1.19 + 0.24 | **0.18 + 0.75** |
| 16k | **1.08 + 0.25** | 0.18 + 1.66 | **1.11 + 0.24** | 0.19 + 1.83 |
| 65k | **1.16 + 0.24** | 0.20 + 3.85 | **1.06 + 0.41** | 0.17 + 5.78 |
| 262k | **0.42 + 0.79** | 0.08 + 17.8 | **0.42 + 0.90** | 0.07 + 24.8 |

- **Crossover ~8k** (points or ~70 px segments): below it the one-pass compute raster is cheaper in total and almost
  free on the CPU; above it the Render TOP wins (its GPU raster is ~flat, the brute-force tile walk is linear in N).
  A counting-sort raster (histogram, prefix, scatter, accumulate) would be 4 compute passes = ~0.4-0.8 ms CPU + ~1 ms
  GPU fixed (T-143 (6): ~0.2-0.3 ms GPU per small compute pass): no better than the Render TOP at 65k. Not built.
- Parity at 270x480, 65k points: alpha sum 19417 vs the render's 19418, 153 pixels (0.8 %) one pixel over (the same
  point-centre rounding share as GEN_points vs numpy, 0.6-0.9 %). uint fixed point cannot add negative weights.
  The line kernel is anti-aliased 1-px coverage; the Render TOP draws aliased lines: a different look, not parity.
- GLSL TOP facts seen: inputs cannot be wired across COMPs (`inputConnectors[0].connect` to an op in the parent did
  nothing; compile error "sTD2DInputs undeclared"): use a Select TOP inside. The GLSL TOP has an **Atomic Counters**
  page (global counters) and a **Buffers** page (POP attributes) on 31550: both are GPU-structure work (T-124), not
  probed here.

## The recipe (for every owner)

1. **Count Render TOPs, not points.** Each Render TOP (and each Render Pass TOP) costs the full fixed CPU (~0.3-1.2 ms
   here at load 20-60, 2+ ms under heavier load) whatever it draws; extra Geometry COMPs inside one Render TOP cost
   +0.05-0.15 ms. Merge geos into one Render TOP; never add a Render Pass TOP for a second layer.
2. **Don't tune render pars for CPU.** Resolution, format, AA, depth format, dither, lights, camera, count, instancing
   and MAT type move GPU time only (or nothing).
3. **Cook triggers first.** Anything that pulls a render (a visible viewer of a downstream op, a TOP `.width` read in
   an expression, T-143 (3), a time reference in a camera read by a Script CHOP, T-185) makes it pay every frame.
   Disabled / bypassed parts must stop at a Switch whose index already says "off" upstream of the render (a bypass
   Switch downstream does not stop a viewer pull).
4. **Time-dependent uniform expressions cost ~4 us each per frame;** static ones are cached (free). Keep per-frame
   values to a few uniforms (one time / drive vec4).
5. **Small counts (<= ~8k points or segments): one compute raster pass** instead of a Render TOP (CPU 0.1-0.2 ms,
   GPU 0.3-0.75 ms at 1-4k). Above ~8k keep the Render TOP.
6. Measure paired, same frames; absolute floors move 3x with machine load.

### Per owner (not changed here)

- **PX_pointfx / PX_lines:** PX_lines draws in its own Render TOP: drawing `lgeo` as a second geo in PX's sprite render
  saves one floor (~0.7-1.9 ms CPU; px.md "Open (wave 2)" already proposes it). The sprite render is 262k instanced
  quads: keep it a Render TOP (rule 5 does not apply).
- **BO_particles:** dots + PX_lines light trails = two floors; one Render TOP with both geos (rule 1). Bloom 1.8-2 ms
  GPU is separate (light-trail presets already ship Bloom 0).
- **FX_track plexus:** segments are tracker-pair lines, typically a few thousand: the compute line kernel (rule 5)
  would replace PX_lines' Render TOP (2.0-2.7 ms CPU) with ~0.2 CPU + ~0.3-0.75 GPU, if the AA line look is accepted.
- **FX_synth ruttetra:** Lines 120 x Samples 256 = 30 k segments: over the crossover; keep the Render TOP. Lower line
  counts (<= ~32 x 128) could use the compute kernel.
- **Any rack with per-slot mix Cross TOPs:** same viewer pull as GEN_points when the pane shows the rack. **Fixed for
  every rack built on `fx_glitch.py` / `gen_pattern.py`** ("Applied: slot_gate" below).

## Applied: GEN_points (builders/gen_points.py)

`out_sel` index = 0 (in1 passthrough, nothing upstream cooks) when Amount 0 **or the rack slot is off (enabled 0 or
mix 0)**: `OUT_SEL_E`. Enabled modules are unchanged.

- **Before -> after, b3, pane on the rack, viewers on, 1 of 12 slots enabled, 4 interleaved runs:** GEN_points
  68.0 / 70.0 ms -> **8.5 / 11.2 ms per frame** (cpu + gpu of its ops, test clip excluded), renders per frame 12 -> 1,
  b3 real fps 12.7 / 12.5 -> 43.4 / 27.0 (load average ~60).
- Pane off (normal pulls): unchanged path; density2d1 solo 4.6 ms median (render CPU 2.1 at that load).
- Parity on b3 after the change (density2d1, preset 3 + Persist 0, Glow 0, float, frozen): step max rel 4.7e-7,
  render alpha / rgb sums exact (65536 / 65536), look within tol 1.0 (max 0.053 tol units). Slot toggle:
  attractor3d1 enabled -> index 2, 114 render cooks in 3 s; disabled -> index 0, 0 cooks; td_errors 0.
- Main (27 Oct ~00:55Z, quiet): same expression set on the 12 `out_sel` ops by the builder constant (one exec), next
  exec: indexes [2, 0 x 11], errors 0, density2d1 render alpha sum 65536; parked; saved `JazibTD_home.722.toe`.
  b3 saved `Build3.257.toe`. Offline: test_gen_points 31 OK.

## Applied: slot_gate in every shared rack (builders/fx_glitch.py, builders/gen_pattern.py; 27 Oct, b3 -> main, T-201)

Each module COMP gets a `slot_gate` Switch TOP right before `out1`: index `SLOT_GATE_E` = 0 (in1, nothing in the module
cooks) when its `slots` row is off (enabled 0 or mix <= 0, the same test as the rack's `<name>_slot`), else 1 (the
module's own output, untouched). Made by the racks' `_instance` (build / add / upgrade) and by `gate_upgrade(comp,
name)` (gate only: re-applies the module's stored stage plan, no shader / par / preset rebuild; the main path). A
module whose out1 already comes from a slot-aware `out_sel` (GEN_points `OUT_SEL_E`) is left alone. Racks covered:
FX_glitch, FX_analog, FX_stylise, FX_glass, FX_scope, FX_synth, FX_track, GEN_sim, GEN_interactive (fx_glitch.py);
GEN_pattern, GEN_sdf (gen_pattern.py). The copied racks have the same block in their own `_instance`: FX_destroy,
FX_retro (this lane), FX_film (perf lane 3, commit 3965115).

- **b3 (31550), pane on the rack, all viewers on, 1 slot enabled, before -> after (5 s windows, warm-up window
  dropped; ms = cooks per frame x last cpu+gpu, noisy):** FX_analog (6 slots) shader passes per frame 16 -> 3, ops
  cooking 54 -> 38, ~6-8.5 -> ~2.3-5 ms; GEN_pattern (17 slots) 17 -> 1, ops 90 -> 11, 11.8 -> 1.8-2.0 ms; GEN_sim (4
  slots, via `gate_upgrade`) 9 -> 2 passes, 1.9-4.4 -> 1.1-2.2 ms. b3 held ~60 fps throughout (light load).
- **Parity (b3, numpyArray, same frame):** every gate on: out1 == the module output, max diff 0.0, same pixel format;
  every gate off: out1 == in1, diff 0.0 (FX_analog 6, GEN_pattern 17, GEN_sim 4). Toggle: FX_analog vhs1 enabled 1 ->
  gate 1, its 4 passes cook, out1 == out_sel diff 0; back to 0 -> gate 0, passes stop, out1 == in1 diff 0. Layout check
  after `gate_upgrade`: ok (no overlaps / intruders / unboxed). GEN_points: `gate_upgrade` skips (out1 = out_sel).
- **Main (27 Oct ~01:15-01:40Z):** `gate_upgrade` per rack, one rack per exec, then a read-only check that every gate
  index agrees with its `<name>_slot` index and errors under the rack = 0: GEN_pattern 17, GEN_sdf 10, GEN_sim 8,
  FX_analog 6, FX_stylise 8, FX_glass 5, FX_scope 5, FX_synth 7, GEN_interactive 7, FX_glitch 16 gates (misc1 already
  gated by the misc lane's upgrade). Saved JazibTD_home.742 / .746 / .748 / .754. FX_track: see the rack doc.
- **Copied racks (b3 relaunched as Build3.279 after a hang during a one-exec 12-module FX_retro build; rebuilt one
  module per exec):** FX_destroy (6 slots, shatter1 on) passes 14 -> 3, ops 39 -> 26, ~4.3-10 -> ~2.7-4.2 ms; FX_retro
  (palette1 on + dither1 off) 2 -> 1 pass (dither1's gate forced to 1 = the old behaviour, same frames). Parity diff
  0.0 on / off (8 modules); toggles melt1 / dither1 on -> their passes cook, out1 == module output; off -> stop, out1 ==
  in1. Main: FX_destroy 6 gates, FX_retro 12, indexes = `<name>_slot`, errors 0, saved JazibTD_home.770; library
  re-exported. **FX_film in main not gated yet:** main still has the pre-lane-3 FX_film (halation1 `pyr1` chain, no
  `pyra`), so it waits for lane 3's bring-home; then `gate_upgrade` (in fx_film.py) per slot.
- Offline: test_fx_glitch `SlotGate` + `Families` (every fx_glitch-based family uses the gated `_instance`),
  test_gen_pattern the same (GEN_sdf's own `_instance` calls the gate; GEN_points' `OUT_SEL_E` needs none).

## Also: T-190 menu refresh in the rack builder (builders/gen_pattern.py)

`_pars` now refreshes an existing menu par's names / labels when the spec grew (`_refresh_menu`, value kept when still
valid), so GEN_pattern, GEN_sdf and GEN_sim racks (they exec gen_pattern.py) get grown menus on rebuild like
GEN_points / BO_particles. Offline test `MenuRefresh` (test_gen_pattern 36 OK, test_gen_sim 15 OK). **Main not
touched:** a read-only check found no grown menu (GEN_pattern 69 menu pars, GEN_sdf 52: all equal to the spec;
GEN_sim's builder has no `module_ns`, not checked).

## Incident

T-194: b2 / b3 / b4 / scratch died together at 00:09Z. My batch-2 sampler had started 6 s before on b3: 16 variants
force-cooked every frame, among them configs new to this TD (65k-instance geometry, SOP particles, a Render Pass TOP,
two GLSL TOPs). Not proven to be the fault (b4 ran a heavy raymarch at the same time), but the sampler was GPU
pressure; it was rerun light (one pair per batch, 256x256) without any further problem.
