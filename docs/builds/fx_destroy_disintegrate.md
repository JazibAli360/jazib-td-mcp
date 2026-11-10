# fx_destroy_disintegrate: FX_destroy module `disintegrate` (26 Oct 2026, TD 2025.31550; build TD b4, then main)

The picture crumbles into dust that blows away (Thanos snap) and can fly back together (FX1 DG-17, FX4 D4, FX0 backlog
#11). A module of the `FX_destroy` rack (`builders/fx_destroy.py`); the rack finds it by name, nothing in the rack
changed. No new framework: it reuses explode's `hit` latch shader and Beat CHOP exec as they are (exec'd from
`fx_destroy_explode.py`), the rack's Point page (Effector Null / Point uv), Mask page + `fxMask()`, State page +
`pulse_exec`, GLSL lib and compute helper, and PX v2's ember-pool ideas (wind cone, keep colour vs hot tint, lift,
lifespan) re-done in 2D. BO_particles / PX were not used as the engine: the motion is closed-form per grain, so one
compute pass draws it without particle state.

Files: `builders/fx_destroy_disintegrate.py` (PAGES, full-state PRESETS, 3 shaders + explode's latch, `build(m, H)`),
`builders/fx_destroy_disintegrate_logic.py` (numpy reference: release times, flight, particle motion, splat
coverage, remnant; CLI `expect`), `test/test_fx_destroy_disintegrate.py` (16 offline tests incl. glslc compile):
`python3 -I -m unittest discover -s test -p 'test_fx_destroy_disintegrate.py'`.

```python
ns = dict(globals()); exec(open('<repo>/builders/fx_destroy.py').read(), ns)
ns['add']('/project1/lab/FX_destroy', 'disintegrate')      # disintegrate1, wired last, zkit panel + 5 presets
```

## How it works
| Op | What |
|---|---|
| `hit` | explode's latch (2x1 rgba32float in place): Trigger / Beat CHOP rising edge / Auto -> hit time + centre px (Effector Null tx/ty + 0.5, else Point u/v); Reset clears; `Ignorehits` drops hits until Sweep + Hold + Return (assemble: Sweep + Duration) |
| `grains` | compute at grain resolution + 1 row (texel (0, top) = copy of the hit latch for fx) (Grain px; 2 px at 1080x1920 = 540 x 960 = 518400 grains), rgba32float: r = release time `tb` = Sweep x f, g = f, b = mask. f = front (wipe direction at Frontangle / out from the Point / in to the Point / noise / bright first / Mask as a wipe map) mixed with fbm (Roughness, Noisescale, Detail), Reverse, + per-grain Jitter. Mask < 0.5 = never released (except Front = mask, where the mask IS the order) |
| `dust` | compute dispatched one thread per grain, output full res rgba16float, cleared every cook. A released grain flies for tau s: wind (Windangle, Windspeed) inside a Cone with Spread speed variety, Blast from the centre with Falloff and Drag, Gravity (< 0 lifts), curl-noise Turbulence (Turbscale, Turbspeed: neighbours move together = wisps), Push away from the live Effector within Pushradius. Colour = the grain's picture colour (bilinear at its centre), Hot tint cooling over Hottime, Ash darkening over Life; alpha fades over the last 70 % of Life; drawn as a square of Size x Grain px shrinking to Shrink x (loop bound 12 px per side, T-124). Overlaps: last write wins |
| `fx` | full res (3 inputs: picture, grains, dust; the hit latch is read from grains' extra top row, T-138): intact grain = texelFetch of the picture (exact), released = Back (dimmed picture / transparent), Edge glow (Edgecolor) for Edge s before release, then dust over or added (Blend) |

**Time model** (closed form, no state to go stale): age = now - hit (Drive hits) or Progress x Duration (Drive
manual: scrubbing Progress back reassembles). Mode **away**: a grain flies from `tb`; with Return > 0 it flies Hold s
out, then retraces its own path home over Return s (all home by Sweep + Hold + Return = exact passthrough again);
Return 0 = the picture stays gone. Mode **assemble**: every grain starts Duration s out and lands at tb + Duration
(dust flies in along the reversed path). Amount scales the motion, the fade and the Back mix; Amount 0 = exact
passthrough.

Presets (full states, T-124 (1)): 1 **snap** (diagonal ragged wipe, dust drifts right-up, fades 2.2 s), 2 **ash
sweep** (bottom -> top, orange edge glow, hot embers rise and cool to ash, added), 3 **pixel blow** (6 px grains blown
right at 700 px/s), 4 **radial + reassemble** (from the Point/Effector, blast, flies 1.4 s, returns over 1.6 s, blue
edge), 5 **assemble** (noise order, dust flies in from the left-down over 1.8 s). For the show: set Auto or bind
Beatchop, or Drive manual on a fader.

Reference numbers (`python3 -I builders/fx_destroy_disintegrate_logic.py expect`; released share of grains at
manual time t, 1080x1920, centre 540/960):
```
1 snap t=0.5 released 0.0370 t=1.5 released 0.7895 t=3.0 released 1.0000
2 ash sweep t=0.5 released 0.0449 t=1.5 released 0.4950 t=3.0 released 0.9993
3 pixel blow t=0.5 released 0.2881 t=1.5 released 0.9644 t=3.0 released 1.0000
4 radial + reassemble t=0.5 released 0.2656 t=1.5 released 1.0000 t=3.0 released 1.0000
5 assemble t=0.5 released 1.0000 t=1.5 released 0.7167 t=3.0 released 0.0000
```

## LIVE CHECKS (about 20 min on a build TD; FX_destroy un-parked, clip paused, each read 4+ frames after a change, one
TOP readback per exec, no TOP read in the exec that changes it, T-74/T-76)
Parity checks use Drive manual (age = Progress x Duration exactly, no frame-time noise).

| # | Check | Expected |
|---|---|---|
| D1 | `add` disintegrate -> `td_errors` on disintegrate1, GLSL info of hit / grains / dust / fx | 0 errors; panel + 5 presets; `dust` dispatch = ceil(grains / 8) |
| D2 | Passthrough (numpy max abs diff in1 vs out1): no hit; Amount 0 after a Trigger; Drive manual Progress 0; preset 4 after Sweep + Hold + Return; after Reset | 0 in all. Control: preset 1 mid-run diff > 0 |
| D3 | Release times: preset 1 values, Drive manual, Point 0.5/0.5; read `grains` r, compare with `grains()` | max abs diff <= 1e-3 s (float32 fbm); for Front point and dir too |
| D4 | Remnant + dust: preset 3 (Grain 6), Progress so age = 1.0 s; read out1 / in1 / dust alpha; compare dust alpha > 0 with `dust_alpha()` and released pixels with `remnant()` | coverage agreement >= 99 % (float32 positions on pixel edges), remnant agreement >= 99.9 % |
| D5 | Hits: Trigger, Beat CHOP (temp LFO), Auto, Ignorehits, Reset; Effector Null moves the centre | latch as explode (texel 0 time / centre px) |
| D6 | Presets 1-5 recall; one capture mid-run each of 1 and 4 | pars as stored |
| D7 | Cost: preset 1 (Grain 2, 518k grains) mid-run, out1 pulled per frame, 120 frames, median cpu+gpu of hit+grains+dust+fx; idle; Grain 1 | target <= 3 ms; idle ~ copy |

## Verified live (26 Oct, 31550, build TD b4 = main's FX_destroy exported read-only, disintegrate1 added after explode1)
Main TD not touched except the read-only export; checks compare disintegrate1/in1 vs out1 (in1 = the rack chain), clip
paused, every read in its own exec after the change.
- D1: `add` -> 0 errors / warnings on hit / grains (540 x 961) / dust (1080x1920, dispatch 68 x 120, clear on) / fx;
  zkit panel + 5 presets; `td_layout check` ok (12 ops). First try failed on a 4th fx input (T-138), fixed.
- D2 exact passthrough (max abs diff 0): no hit; Amount 0 after a Trigger; Drive manual Progress 0; preset 4 after
  Sweep + Hold + Return (5 s after Trigger; 1.0 at 2 s); preset 5 assemble finished (4 s; 1.0 at 1.5 s); after Reset.
- D3 release times vs `grains()`: preset 1 (dir + fbm) max 8.6e-6 s, preset 4 (point) 2.3e-6, preset 3 (Grain 6)
  1.4e-6; 0 grains over 1e-3. Hit-copy row = latch texel.
- D4 dust + remnant (manual drive): preset 3 at 1.0 s: 36720 particles, dust coverage ref 0.2796 = got 0.2796, agree
  0.99999; preset 1 at 1.5 s: 409277 particles, coverage 0.4436 / 0.4436, agree 0.99992; released share 0.7895 (= the
  table above); remnant on dust-free pixels agrees 1.000000 (intact = exact picture, released = black).
- D5 hits: Trigger latched (time, 540, 960); Effector Null tx 0.2 ty -0.1 -> centre (756, 768); 2 Hz square LFO as
  Beat CHOP latched edges (beat_exec active only while bound); Ignorehits held the hit 3 s; Reset -> -1 (temp ops
  removed after).
- D6: zkit Recall 1-5 -> all 48 pars exactly as stored.
- D7 cost (out1 pulled per frame, 110 frames, median of sum cpu+gpu of hit/grains/dust/fx [max]; b4 with 5 other TDs
  busy, so numbers swing): preset 1 mid-run (Grain 2, 409k particles) 1.96 and 2.77 ms [7-11] (per op medians hit 0.2,
  grains 0.26-0.31, dust 0.31-0.54, fx 0.35-0.42); idle (Progress 0) 1.32; preset 2 1.71; preset 4 1.72; **Grain 1
  (2.07M grains) 3.84 ms** - over the 3 ms aim, use Grain >= 2 for shows. The 2x1 hit pass costs ~0.2 ms (CPU floor).
  Project fps not measured fairly on b4 (6 TDs on the GPU); re-measure on main after bring-home.
- Captures (b4): `output/fx_destroy_disintegrate_snap_out1.png` (preset 1 at 1.5 s),
  `output/fx_destroy_disintegrate_radial_out1.png` (preset 4), `output/fx_destroy_disintegrate_ash_out1.png` (preset 2).
- b4 saved (Build4.19.toe), disintegrate1 left on preset 1 values, Drive hits, Reset (intact).
- **Bring-home: done later** (27 Oct correction; T-138 had refused it, `bring_home.mjs` refused the COMP listed in
  active_lanes by this lane and `--force` was blocked, so it was first left with the main session). Main FX_destroy now
  has `disintegrate1`: the library export of 27 Oct lists the slots checked in main (burn1 crack1 disintegrate1 explode1
  melt1 shatter1) and T-162 rebuilt all 6 modules by builder in main (JazibTD_home.476, td_errors clean, Amount 0 = exact
  passthrough on all six). Not measured on main: the fps / cost numbers above are from b4 only (re-measure on a quiet main).
- **First bring-home, 26 Oct (record added 27 Oct):** FX_destroy (6 modules) went b4 -> main at 21:53 (the selfcheck
  entry stamped 2026-10-26T21:53), ops 1826 = 1826, 0 errors, and main was saved as `JazibTD_home.386` (checkpoint of
  the old main kept). Evidence: `logs/selfcheck.log`, line "disintegrate home: FX_destroy (6 modules) b4 -> main, ops
  1826 = 1826, 0 errors, saved JazibTD_home.386, checkpoint of old kept; b4 free". The bullet above describes the later
  rebuild of all 6 modules by builder in main (JazibTD_home.476, T-162).

## Not done / open
- Overlapping dust squares: the last write wins (GPU order), so where many particles pile up the colour shown is one
  of them, not a blend; alpha fade still reads as dust. True additive splats would need an atomic or Render-TOP
  accumulation pass (T-112 (2)), at about 2 ms more.
- Particles are flat squares (no blur, no rotation, no depth); Size up to 12 px per side.
- A moving Effector with Drive manual moves the radial front live (grains jump); with hits the centre is latched.
