# fx_destroy: FX_destroy rack + 6 modules `melt`, `burn`, `shatter`, `crack`, `explode`, `disintegrate` (26-27 Oct 2026, TD 2025.31550)

`/project1/lab/FX_destroy`. The destruction COMP (FX1 DG-14 / DG-18 / DG-15). It is the **same lean rack as
FX_glitch** (`docs/builds/fx_glitch.md`), copied rather than abstracted: `slots` table (name module enabled order mix),
a slot = module COMP + Cross (`<name>_mix`) + Switch (`<name>_slot`), Panic toggle, zkit panel + presets per module,
`test_clip` / `in1` input. Module X = `builders/fx_destroy_X.py`. No codegen, no registry.

```python
ns = dict(globals()); exec(open('<repo>/builders/fx_destroy.py').read(), ns)
ns['build']('/project1/lab')                          # rack + melt1 / burn1 / shatter1 on first build; idempotent
ns['add']('/project1/lab/FX_destroy', 'shatter')       # shatter2, wired last
ns['remove']('/project1/lab/FX_destroy', 'shatter2'); ns['rewire'](op('/project1/lab/FX_destroy'))
```
Offline tests: `python3 -I -m unittest discover -s test -p 'test_fx_destroy.py'` (5: chain, specs, presets, point expr).

**Shared in the rack** (each used by 2+ modules today): extra par styles (Pulse, RGB, TOP, COMP, CHOP); the **Mask**
page + `fxMask()` GLSL (melt, burn: none / bright / dark / Mask TOP red / radial around the Point, level, softness,
invert; `mask_src` Select pulls the Mask TOP only while Masksource = top); the **Point** page (melt, burn, shatter:
`Effector` Null COMP, its `tx ty` + 0.5 = uv, so the frame spans -0.5..0.5; else Point u/v); a **State** page
(Resettime, Hittime) written by a `pulse_exec` Parameter Execute from the Reset / Trigger pulses, so the shaders compare
times and no Python runs per frame; GLSL lib (lowbias32 hash, value noise, fbm, luma); a compute GLSL helper.

**State rule (all three):** state lives in a compute TOP with `outputaccess readwrite` + `clearoutputs off` (FX6 5a),
each texel stores its last cook time; a gap > 0.25 s (slot bypassed, panic, parked) or a Reset restarts from the intact
picture. All updates are dt-based, so a second cook in the same frame changes nothing.

## Module `melt` (DG-14)
`in1` -> `state` (rgba32float at Quality res: sag px, speed) -> `st_sel` -> `fx` (full res, samples the CLEAN input at
p - dir * sag, `inputextenduv hold`) -> `out1`. Modes: **Melt field** (gravity sag with per-column drip noise, luma
weight, viscosity, Recover pull-back, optional Max sag), **Drip streaks** (per column a start h(x); the colour at h is
stretched by the column's sag with a round drop head), **Heat wave** (no state: sag grows with depth + lateral sine).
Direction down / up / left / right / radial out / in (around the Point). Mask scales the drive. Presets: wax, acid
drip, heat haze, beat sag (Recover 0.6, Max 300), implode (radial in).

## Module `burn` (DG-18)
**Noise dissolve** (one pass): Progress threshold over fbm + an origin front (noise only, bottom, top, Point / 2
Effectors, mask white starts, random sparks), Roughness, Band, Char ahead, Rise (flames scroll up), Fuel from luma.
**Fire spread CA** (`state` rgba32float at Cell 2/4/8 px: burn age, -1 unburnt): an unburnt cell ignites with
probability Spread x (8 neighbours at Reach cells still burning, weighted by wind: Windangle / Windforce) x fuel
(luma) per step; ignition from the origin (edge row, cells within Radius of the Point/Effectors, mask > 0.5, random
sparks). The fx reads the age through a 4-tap, noise-warped lookup (breaks the cell grid), `inputextenduv hold`.
Both map the phase through **hot core -> ember rim -> char -> ash** (Colours page: Hotcolor, Embercolor, Charcolor;
Emissive; Back black / transparent). Maskuse: burn only inside the mask, or ignore it. Presets: paper burn (CA,
bottom), ember rise (noise), acid melt (green palette), wildfire (CA from the Point, wind 30 deg), spark holes.
CA neighbour reads are in place (same dispatch), so a front can occasionally jump 2 cells in a frame: visual only.

## Module `shatter` (DG-15)
`state`: ONE compute TOP, 3 rgba32float colour buffers in place, 64 x 32 texels = one per shard (up to 2048):
b0 pos/vel px, b1 angle / spin / z / alpha (-1 = intact), b2 seen hit / release / vz / last cook; `state_b1` (Render
Select bufferindex 1) feeds the fx. Shards = Voronoi cells of a jittered square grid (Cells across, Jitter).
Hit = Trigger pulse, a Beat CHOP rising edge (`beat_exec`, active only while Beatchop is set) or every Auto s; impulse
from the impact Point/Effector with Falloff, Scatter, Spin, Depth (z kick, scale), Gravity, Drag, Floor + Bounce,
Stagger (release delay by distance), Return spring (critically damped; reassembled shards snap back to exact rest),
Fade, Timescale. `fx` (16x16 workgroups): each tile lists the shards that can reach it in shared memory (atomicAdd,
max 96) with each one's 3x3 neighbour seeds; each pixel inverse-maps through the listed shards (highest z wins),
Voronoi membership in the shard's own frame, crack edge refraction (Refract px) + glow (Crackcolor, Crackglow,
Crackwidth); holes show Back (dimmed picture, Backdim 0 = black, or transparent). Tiles with nothing moving copy the
input. Presets: screen smash, slow-mo glass, reassemble on beat (Auto 1 s, Return 6), explode, floor tiles.

## Verified live (26 Oct, 31550; main TD with other lanes cooking; every shader first on the scratch TD)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- **Exact passthrough** (img_src vs out1, numpy max abs diff, clip paused, read >= 4 frames after each change, separate
  execs): melt Amount 0 -> 0, slot enabled 0 -> 0, mix 0 -> 0, Panic on (Amount 1) -> 0; burn Amount 0 -> 0, Progress
  0 -> 0; shatter Amount 0 -> 0, intact (before a hit and after Reset) -> 0, **after Return reassembly -> 0** (scratch:
  144/144 shards back at rest in 3.3 s).
- **melt** (field, defaults, 1.13 s after Reset): mean sag 65 px, column sag 10th-90th pct 30-134 px (streams),
  95 % of pixels changed, mean diff 0.085; streaks 50 % changed; heat wave 76 % changed. Reset -> sag 0 next frame.
- **burn**: noise, bottom origin, Progress 0.5: 62 % changed, 43 % ash, bottom quarter 98 % ash / top quarter 0 %,
  2.6 % ember-glow pixels. CA from the Point (0.5, 0.35), Spread 0.8, Reach 2: 74 % of cells burnt after 2.6 s, the
  front reached row 405 upward vs row 5 downward from row 168 (wind up). Frame edge clean after `hold` (0 % edge px).
- **shatter** (Cells 9 = 144 shards, defaults, 1.18 s after Trigger): 144 broken, mean travel 895 px, mean vy
  -1476 px/s, mean |angle| 1.47 rad, 60 % hole pixels. Effector Null `/project1/lab/PX_pointfx/effectors/E2`
  (tx -0.8, ty 0.3) -> impact (-324, 1536) px, cleared -> Point.
- **Cost** (out1 pulled per frame, sum cpu+gpu of the COMP's TOPs cooked that frame, test clip excluded, median [max]):
  melt field 0.66 [1.9], streaks 0.82 [2.2], wave 0.55 [2.8]; burn noise 0.76 [2.6], CA 1.25; shatter intact 0.88,
  flying 1.47 [1.8] (was 3.24 before the per-tile neighbour-seed cache); **all three chained 3.14 ms** [4.6]. Each
  module < 3 ms, so no Quality par beyond melt's state res and burn's Cell. Project rate this hour was set by other
  lanes: pull-only wall clock median 21.8 ms per frame with FX_destroy pulled AND without it (pane on FX_glitch);
  td_watch earlier 60.2 fps with the COMP cooking. Shader compile on first cook ~250 ms CPU each (one-off hitch).
- `td_errors` clean, `td_layout check` ok (rack + 3 modules), checkpoint
  `output/checkpoints/FX_destroy/FX_destroy_20261026-194828.tox`, project saved (.256), COMP parked.
- Captures: `output/fx_destroy_melt_out1.png`, `output/fx_destroy_burn_noise_out1.png`,
  `output/fx_destroy_burn_ca_out1.png`, `output/fx_destroy_shatter_out1.png`, network `output/fx_destroy_melt_net.png`.

## Glass look (D11) - `shatter` Look = glass (26 Oct; live on b3 + main, see "Verified live (glass)")
FX4 D11 / FX0 row 76, folded into `shatter` (no new module). Ideas from `td-port/prism_glass` (per-channel offset
along the slope: R bends least, B most). Only flying shards change; **intact shards stay the exact picture**, so the
passthrough guarantees hold (Amount 0, intact before a hit, after Reset, after Return reassembly). Same single fx
compute pass, same 3 inputs, same shared-memory tile list; 4 more vec4 uniforms (uL uT uN uR) and 2 more texture
taps per flying-glass pixel (est. +0.1-0.3 ms over flat's 1.47 ms flying).

Per flying shard pixel (shader `glassSlope` / `glassShade`; numpy mirror `builders/fx_destroy_shatter_glass_logic.py`):
slope = Tilt x hash vector per shard (lowbias32, Seed + 911) turned by the shard angle x (1 + z) + bevel (-inward edge
normal x (1 - edge/Bevel)^2); offset = slope x Thickness x (1 - 1/Ior); R / G / B read at offset x (1 - D) / 1 /
(1 + D); x Glasstint; + Rimcolor x (Fresnel rim + spec), rim = Fresnel x (F - F0)/(1 - F0) with Schlick F (0 on a
flat face), spec = Specular x Blinn (light at Lightangle, 45 deg up) ^ Shine. The flat look's crack-edge refract is
replaced by the bevel; Crackglow still adds on top.

| Par (page Glass) | What |
|---|---|
| Look | flat (default, the old look) / glass |
| Ior | 1 = no bend; 1.5 glass |
| Thickness | px; offset = slope x Thickness x (1 - 1/Ior) (slope 1, Ior 1.5, 60 px -> 20 px) |
| Dispersion | R/B split (0 = no fringes) |
| Tilt | per-pane random tilt (grows with z kick) |
| Bevel | px from the edge where the pane slopes off (0 = none) |
| Fresnel, Specular, Shine, Lightangle | rim + highlight (Rimcolor) |
| Glasstint, Rimcolor | RGB |

Presets: every preset now sets Look (partial presets inherit, T-124 (1)); **`slow-mo glass` (slot 2) uses Look glass**
(Ior 1.5, Thickness 70, Dispersion 0.35, Tilt 0.4, Bevel 16, Fresnel 1, Specular 0.5, Crackglow 1.8 -> 0.6); the other
four keep Look flat, so they look exactly as before. Tests: `test/test_fx_destroy_shatter_glass.py` (17: glslc state +
fx, uniforms declared == set, pars exist, 3 inputs, presets, numpy maths).

### LIVE CHECKS (b3 first; clip paused, reads in a separate exec >= 4 frames after a change, T-74)
1. **Builds clean:** rebuild the rack (`build` is idempotent; adds the Glass page) -> `td_errors` none, `fx` compiles.
2. **Passthrough:** Look glass, Amount 0 -> max diff 0; intact (Reset, before a hit) -> 0; Return 6 after
   reassembly -> 0.
3. **Flat unchanged:** Look flat, Seed 1, defaults, Timescale 0 after a hit at a fixed state: out1 equals the
   pre-change build (or: Look flat out == Look glass out where no shard flies; and flat out vs a checkpoint of the old
   shader text in a copy, max diff 0).
4. **Dispersion at edges:** glass, Tilt 0.6, Dispersion 0.5, after a hit, Timescale 0 (freeze): over flying-shard
   pixels mean |R - B| shift vs the flat look clearly > 0; Dispersion 0 -> per-pixel R, G, B come from one offset
   (vs reference below, max err <= 2/255).
5. **Parity vs numpy** (Bevel 0, Fade 0, Depth 0 or any, Amount 1, Crackglow 0, frozen with Timescale 0 a few
   frames after a hit): in one exec read `in1`, `state` (b0), `state_b1`, `out1` numpyArrays, then
   ```python
   import sys; sys.path.insert(0, '<repo>/builders'); import fx_destroy_shatter_glass_logic as G
   m = op('/project1/lab/FX_destroy/shatter1'); P = G.pars_from_comp(m)
   pts = G.live_points(img, b0, b1, img.shape[1], m.par.Cells.eval(), m.par.Jitter.eval(), P)
   ok = sum(abs(out[y, x, :3] - e[:3]).max() <= 3 / 255 for x, y, e in pts) / len(pts)
   ```
   Expect >= 90 % of shard centres match (overlaps / crack glow near tiny shards account for the rest).
6. **Cost:** flying glass (Cells 9 and 14) median per pulled frame <= ~1.8 ms (flat 1.47); project fps 60.

### Verified live (glass: 26 Oct, 31550; b3 then main)
- b3 (FX_destroy loaded by tox from main; shatter1 rebuilt from the builder, Glass page, preset rows refreshed):
  td_errors none. Look glass: Amount 0 -> **0**; intact after Reset -> **0**; Return 6 reassembly (Gravity 0) -> all
  144 shards back, diff **0**.
- Flat unchanged: a temporary copy of `fx` running the pre-glass shader text vs `fx` (Look flat), state frozen
  mid-flight (Timescale 0, 99 % of pixels changed): max diff **0.0**.
- Parity vs `live_points` (Tilt 0.6, Bevel 0, Crackglow 0, Stagger 3, frozen 0.2 s after the hit so shards don't
  overlap): **97.9 %** of 144 shard centres within 3/255 (median 0.0016), Dispersion 0.5 and 0. Mid-flight (0.5 s, shards
  overlap) 62.5 %: the helper doesn't resolve overlaps, as its doc says. R/B fringes vs flat: |d(R - B)| mean 0.047 on
  the 98 % of pixels glass changes.
- Presets: zkit Recall 2 -> Look glass, Thickness 70, Dispersion 0.35, Crackglow 0.6, Cells 14, Timescale 0.25; Recall 1
  -> Look flat. Capture `output/project1_lab_FX_destroy_out1_2026-10-26T18-35-05-727Z.png` (slow-mo glass).
- Cost: paired A/B in the same frames (T-145; a copy of fx with Look forced flat): glass / flat GPU ratio **0.91**
  (2.34 vs 2.47 ms under b3 load), i.e. the glass look costs no more than flat. Absolute medians under load (5 TDs):
  1.3-4.2 ms per frame for the whole module (Cells 14), dominated by load noise.
- **Bugs found + fixed here (T-155, T-160):** Hittime / Resettime stamps from another clock (tox moved from main, or a
  relaunch: main's pars held 10554 / 10606 s while absTime was 2131) made every hit count as already seen; Reset
  compared `>` with the last cook time and never fired when the state had cooked earlier in the pulse's frame. The state
  shader now voids future stamps (also a stored seen hit) and resets on `>=`. b3 with future stamps (+5000 / +6000 s):
  Trigger -> 144 fly. **Every module now (T-162):** the rack's `stamp_expr` / `hit_expr` void future stamps in the
  uniforms (before the Auto max, so Auto works with a stale Hittime); crack / explode (+ disintegrate) clean a stored
  seen stamp > now; melt / burn / crack Reset `>=`. Live b3 (Build3.131) + main by builder (JazibTD_home.476). After a
  tox move or relaunch, set stale State pars to -1: a voided stamp turns valid once the clock passes it (one phantom hit).
- **Main** (JazibTD_home.460, shader comment refresh pending the next rebuild): shatter1 rebuilt by builder, Glass page,
  preset rows refreshed, 1826 ops = b3, td_errors none; Trigger with the stale stamps -> 144 fly; Reset -> intact
  diff 0; Look left flat (default); FX_destroy parked.

## Not done / open
- No audio hook beyond shatter's Beat CHOP; melt Recover / burn Reset can be driven by MIDI/CHOP exports.
- Burn has no particle embers (DG-17 dust layer) and no Erode / Frost / Hologram variants.
- Shatter flat look has no lighting (glass look: refraction, rim, spec only; no shadows); a tile lists at most 96 shards (Cells > ~30 with big Depth could drop some).
- A heavy hitch > 0.25 s restarts melt / burn state (by design); shatter keeps a hit that lands during the hitch.

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (JazibTD_home.770).
