# gen_interactive: GEN_interactive rack + 4 people-driven artist looks (live in main, 26 Oct 2026, TD 2025.31550)

`/project1/lab/GEN_interactive`. FX0 row "GEN_interactive" (backlog ranks 42 + 68): FX5 E8 ribbon brush (Zach
Lieberman look), E4 flowers / waterfall (teamLab look), E1 data pigment (Refik Anadol look), E3 line volumes (Joanie
Lemercier look). Technique emulation only: neutral par names, no frames / logos / assets of the artists; credits are
these names in this doc.

**Status: all four modules verified live on 2025.31550 (build TD b4, 26 Oct): see "Verified live". 92 offline tests.** Offline tests: `python3 -I -m unittest discover -s test -p
'test_gen_interactive*.py'` (rack, points logic, mask, fake-TD builder dry run, glslc compile of every pass against TD
compute stubs = a syntax / type check, not a TD compile, numpy references per module).

## Design (lean: the GEN_sim rack reused, only what every module reads is added)
- **Rack = GEN_sim's** (`builders/gen_sim.py`, itself FX_glitch's): `slots` table, per slot module COMP -> `_mix`
  (Cross) -> `_slot` (Switch 0 bypass / 1 module / 2 mix), Panic, background Input auto / black / live / test clip
  (the stored webcam clip `media/webcam/webcam_ref_5s.mp4`), add / remove / rewire. Each module draws over its slot
  input (Colour page Blend: replace, over, add, screen, multiply, lighten, difference, alpha out premultiplied).
  Amount 0 = `out_sel` passes in1 untouched (nothing in the module cooks).
- **Points** (`pts` Script CHOP -> `pts_tex`, Maxpoints x 1 rgba32f, texel i = x y vx vy; x y in 0..1 of the frame,
  y up; velocity in frame units / s; absent = x = y = -10). Points page `Source`:
  `demo` (Lissajous / orbit / wander / dance paths, no sensor), `face` (FT_face_track `out_pts` landmarks, glob
  `Facepts` on `f<n>_<region>_<kk>`, stride, mirror; zeros = absent), `effectors` (the shared list
  `/project1/effectors`: `Effselect` all / names / #tag through `eff_rt` (CPU twin of the selection); point sets give
  their points, other rows their centre, mapped from the world plane Planecx / cy / w / h, default = BN_fluid2d's
  1.125 x 2 plane), `null` (Null COMPs `Nulls`, default the rack's own `pen1`: move its tx / ty), `mouse` (Mouse In CHOP;
  Mousepen = only while pressed), `chop` (any CHOP: x y 0..1, tx ty -1..1, or world plane). One-pole Smooth (share
  kept per 1/60 s, frame-rate independent), velocity from the smoothed positions. State lives in the callbacks
  module's memory (T-123 (2)), logic in `gi_logic` (copy of `builders/gen_interactive_logic.py`).
- **Mask** (`gi_mask`, Maskw x Maskh 270 x 480 rgba16float, one compute pass + feedback): r = presence (Masksource
  none = 1, top = a mask TOP's r / a / luma, e.g. `CV_person_mask/out2` or `FT_face_track/out_face`, luma = smoothstep
  of the background's luma), g = motion (|luma - last luma| x Motiongain, one-pole Motionsmooth per cook), b = luma.
  Modules read it through a Select TOP `mask`.
- **Drive** (rack page, GEN_pattern's `_drive` imported, not copied): `drive` CHOP = beats (internal Bpm or a beat
  CHOP), bpm, level (any audio CHOP channel); Resync pulse. Module **Drive** page (every module): Speed, Beatgain +
  Beatdecay (pulse = gain x exp(-age / decay) after each beat), Audiogain (x rack level), Manual (0..1 by hand / MIDI);
  shaders get `uDrv` (beats bpm level 0) + `uDg` (the four pars).
- **State** (every module): Reset pulse -> Resetcount + 1 = new epoch; state passes clear on a new epoch or a size
  change. State passes are **self-clocked**: a meta texel holds (.., module time T, last absTime, epoch), a cook in a
  new frame adds dt x Speed (dt capped 0.1 s), a second cook in the same frame copies (readbacks never step it),
  Speed 0 = frozen (deterministic checks).
- **Presets are full states** (`full_presets`: page defaults + the preset): a recall never inherits (T-124 (1)).
- **Drawing without Render TOPs:** lists of primitives (segments, flowers, ...) are drawn by one compute pass with
  16x16 workgroups that walk the list in chunks of 256 (one per thread), keep those touching the tile, pack them with
  an ordered prefix sum (no atomics, as GEN_sim blobs) and shade the packed list per pixel: any count, nothing
  dropped, cost grows with what is near each tile. No POP / MAT / new GPU buffer layouts (T-124); <= 3 inputs per
  GLSL TOP (T-88); no built-in limits (the user rule): width / glow / counts are open ranges, the operator decides.

Files: `builders/gen_interactive.py` (rack), `builders/gen_interactive_logic.py` (points, smoothing, packing, drive,
mask twin), `builders/glsl/gen_interactive_common.glsl` + `gen_interactive_mask.glsl`, per module
`builders/gen_interactive_<m>.py`, `builders/gen_interactive_<m>_logic.py`, `builders/glsl/gen_interactive_<m>_*.glsl`,
tests `test/test_gen_interactive.py` (rack + fake TD + helpers) and `test/test_gen_interactive_<m>.py`.

Build / edit (td_exec):
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_interactive.py').read(), ns)
ns['build']('/project1/lab')                              # rack + ribbon1 (first build); idempotent
ns['add']('/project1/lab/GEN_interactive', 'flowers')      # flowers1, wired last (zkit panel + presets)
ns['preset']('/project1/lab/GEN_interactive/ribbon1', 3)   # full-state preset
ns['remove']('/project1/lab/GEN_interactive', 'flowers1')
```

## Modules
| Module | What | Passes (inputs) | Est. GPU ms 1080x1920 |
|---|---|---|---|
| ribbon | gesture ribbons / multi-line brush following the points: Catmull-Rom smoothing, width by speed (or calligraphy, constant), age fade + taper, strands, wobble, colour by ribbon / direction / age / speed / source picture, solid / light / outline + glow | hist (hist_fb, pts) -> segs (hist, in1) -> cbox (segs) -> fx (in1, segs, cbox) | live: fx 0.49 GPU at defaults (2280 segments) |
| flowers | procedural flowers (6 species, 5-9 SDF petals) bloom where people stand still, petals scatter and fall when they move, die and grow again; waterfall streaks part around people | state (state_fb, mask, pts), water (water_fb, mask) -> fx (in1, state, water) | live: fx 0.9-1.6 GPU (230 flowers), 3.5 dense frame-filling meadow (356) |
| pigment | colour-carrying particles in a curl-noise flow, pushed / pulled / swirled by the points, attracted to / repelled by the mask, or carried by BN_fluid2d velocity; colour from the picture, an image atlas (cross-faded cells = "latent morph") or palette | state (state_fb, pts, field) -> splat (state, colsrc) -> trail (splat, trail_fb, state) -> fx (in1, trail) | live: module 1.76 total (fx 0.38, state 0.18 GPU) |
| linevolume | wire Platonic solids (Nest copies), tonal hatch sphere, relief grid (Joy-Division 3D, hidden lines), moire planes; hairlines of light + glow, depth fade; points move / turn the volume, mask raises the relief or reveals | fx (in1, pts, mask) + clock CHOPs | live: fx 0.5 hatch / moire, 1.1 wire, 1.4 Nest 4, 1.6 relief |

### ribbon (FX5 E8)
- `hist`: Length x (Ribbons + 1) rgba32f ring; row i = ribbon i = point Pointstart + i (x y px, t, valid; absent =
  pen up), last row = meta (head, T, last absTime, epoch / last sample time, samples). Sampleevery 0 = every frame.
- `segs`: 3 x (Length - 1) x Subdiv wide, Ribbons x Strands high; per segment (p0 p1) (w0 w1 a0 a1) (rgb valid).
  Width law constant / speed (Width x speed / Speedref) / calligraphy (Width / (1 + speed / Speedref)), clamped to
  Widthmin..Widthmax (the operator's range), x (1 - Taper x age / Fade), x (1 + beat pulse + audio + Manual). Alpha =
  (1 - age / Fade)^Fadecurve (Fade 0 = never fades; the ring length then bounds the stroke). Strands offset along the
  curve normal by (s - (S-1)/2) x Spread x width / Width; Wobble = value noise keyed by the sample time (sticks to the
  stroke; Wobblespeed makes it crawl).
- `fx`: tapered capsules with 1 px AA; Style solid = the strongest segment wins (clean joins), light = additive,
  outline = |sd| < Edge / 2; Glow = exp(-sd / Glowwidth) halo in every style.
- Presets: 1 light brush, 2 calligraphy, 3 multi line (7 strands), 4 wobble neon, 5 source paint, 6 beat burst.

### flowers (FX5 E4)
- `state` (128 x (ceil(Count / 64) + 1) rgba32f, self-clocked): slot A = (x px, y px, birth T, life), B = (seed, size
  px, scatter T or -1, species); last row meta. Life: bloom over Bloomtime (smoothstep open) -> hold -> wilt (last
  Wilttime s go grey x Wilt) -> petals fall (0.15 x Scatterspeed) for Falltime -> empty -> respawn.
- Births: each empty slot tries one hashed spot per cook, accepted with chance Spawnrate x dt x (1 + beat + level) x
  presence x still^Stillness (still = clamp(1 - motion / Scatterthresh)); with chance Nearshare the spot is near a
  present rack point (+- Spawnnear px). Scatter: motion at a flower above Scatterthresh / (1 + level) -> petals fly
  (hashed outward + upward kick, Petalgravity, Wind, Spin), slot empty after Falltime.
- `water` (Mode waterfall / both): drops from above the top under Gravity / Wind; inside presence > 0.5 the velocity
  into the body is removed along -grad(presence) and Part pushes them out; splash streaks at the hit.
- `fx`: tile lists (chunks of 256) of flowers then drops, painter's order, premultiplied over, then gs_blend.
- Presets: 1 meadow, 2 blossom wind, 3 night lotus, 4 waterfall, 5 falls + blossoms, 6 beat bloom, 7 touch scatter.

### pigment (FX5 E1; the AI image-model side of that work is offline and not attempted)
- `state` (2 Side x (Side + 1) rgba32f, self-clocked; texel 2i = x y age life, 2i+1 = anchor x y (colour sample
  point, pulled to the particle at Morph per s), seed, speed). Velocity (px/s) = Flowstrength x (1 + beat + audio +
  Manual) x curl of an fbm potential (Flowscale, Octaves, Evolve) + Fieldsource mask: Maskforce x grad(presence) x 100
  (+ attract, - repel) or flowtop: Flowgain x field.xy x (frame H / field H) (BN_fluid2d out2 = cells/s at sim res,
  square cells assumed) + per point within Radius: (1 - r/R)^2 x (Pointforce push / attract / swirl + Pointvel x the
  point's velocity). Respawn after Life (+- Lifevar) or off-frame (or wrap); Spawnmode frame / points / mask / bottom.
- `splat` (Quality x frame, 16F, one thread per particle, clearoutputs on, last write wins, T-138): a Size px dot;
  colour = slot picture at the anchor / atlas cell (Atlascells^2, cell advances at Atlasrate, smoothstep cross-fade) /
  palette by speed / age / seed. `trail`: max / add / paint over the last trail x exp(-dts / Trail). `fx`: upsample +
  18-tap ring glow + Exposure, gs_blend.
- Presets: 1 pigment flow, 2 data atlas, 3 ember swirl, 4 person bloom, 5 fluid ink (set Flowtop =
  /project1/lab/BN_fluid2d/out2), 6 beat burst.

### linevolume (FX5 E3)
- One stateless pass; camera at (0, 0, Dist) looking down -z, f = 0.5 / tan(Fov / 2); rotation Rz Ry Rx = Rot + Spin x
  T (+ beat x Kick on y); offset = Pos + Follow x point (first present point or centroid), Followrot turns it.
- Scenes: wire (solid tables of 50 vertices / 90 edges written into the shader from the logic file, Nest copies),
  hatch (ray-sphere hit, object-space stripes Hatchdensity per diameter, duty from the light angle, cross set, rim),
  relief (Rows lines from z = Size to -Size, tilted, raised by Height x field = mask r / luma / noise, hidden lines),
  moire (two gratings, Moireangle, Moirescale, Drift). Lines = 1 px AA band of Linewidth + Glow x exp(-d / Glowwidth).
- Module time = GEN_pattern's clock (`clock` rate -> `clock_int` Speed CHOP + Phase), so the pass has no clock input.
- Presets: 1 wire icosa, 2 nested cubes, 3 hatch sphere, 4 relief grid, 5 person relief, 6 moire planes, 7 follow solid.

## LIVE CHECKS (live lane on build TD b4, ~10 min per module)
Rules: `python3 tools/lane.py add /project1/lab/GEN_interactive "GEN_interactive (b4)"` while building (remove it right
before the bring-home, T-138); one structural change per call + `td_errors`; state reads in a separate exec >= 3
frames after a change (T-116 (4)); no TOP pixel reads in the exec that changes a TOP (T-74 / T-76); measure cost with
the pane off the COMP. Exec preamble: `ns = dict(globals()); exec(open('<repo>/builders/gen_interactive.py').read(), ns)`.

| # | Check | Expected |
|---|---|---|
| I1 | `build('/project1/lab')`, then `td_errors` on the rack and ribbon1 | no errors (GLSL compiles on 31550; a redefined-symbol error names the clash) |
| I2 | rack ops | `pts` 16 samples x (x y vx vy); `pts_tex` 16 x 1 rgba32f; `gi_mask` 270 x 480; `drive` beats bpm level; `slots` 1 row; second `build` = same op counts |
| I3 | Source demo: `pts` read twice 1 s apart | 16 present points, all in 0..1, moving (velocities non-zero) |
| I4 | Source face (FT_face_track on the webcam clip, if present), effectors (`all`), null (`pen1` tx 0.5625 -> x 1.0), chop | points follow; absent face -> x = -10 |
| I5 | Mask none / luma (Input test) / top | presence 1 / follows the clip luma / follows the TOP; motion > 0 only while the clip plays |
| R1 | ribbon1 on Input test, Source demo, after 2 s: `hist` meta | head advances 1 per frame, samples = frames, T = absTime span x Speed |
| R2 | freeze (ribbon1 Speed 0), next exec: read `hist` (numpyArray) -> `gen_interactive_ribbon_logic.segments(hist, pars)` vs `segs` numpy | p0 / p1 / widths / alphas within 1e-3 px / 1e-4 for every valid segment (same count) |
| R3 | same frozen state: `draw()` at 300 random pixels vs `out1` | within 2/255 at >= 97 % of pixels (8-bit output) |
| R4 | each preset 1..6 (frozen after 2 s of demo motion) + one capture | non-flat, looks as named |
| R5 | Amount 0 / slot enabled 0 / Panic | out1 = in1 / img_src exactly (max abs diff 0) |
| R6 | cost, pane off, 120 pulls (`cost_start` / `cost_read`): module total cpu+gpu | <= 3 ms (default preset); report preset 3 (7 strands) too |
| F1 | add flowers; td_errors on flowers1 | state, water, fx compile; <= 3 inputs; `pts` / `mask` resolve to the rack's pts_tex / gi_mask; state 128 x 8 at Count 400, water 128 x 20 at Drops 1200 |
| F2 | one-cook parity: read state_fb, state, mask, pts in one exec; `flowers_logic.state_step(prev, mask, pts, now, pars)` (now = meta z) | slots within 1e-3 px / 1e-4 s; births equal (same hash3), at most 1 of 400 on an exact threshold; water_step positions within 1e-2 px |
| F3 | freeze (Speed 0), read state twice 1 s apart | identical, no births |
| F4 | Masksource top with a box mask (x 0.3-0.7, y 0-0.6), motion 0, defaults, Reset, 2 s | all flowers inside the box; ~87 living at 60 fps (60-110 at the real fps) |
| F5 | moving mask (motion > Scatterthresh) | scatter T set on every flower in the moving area next cook; empty after Falltime + 1 frame |
| F6 | waterfall (preset 4) over the box mask | drops in the box core < 25 % of a Masksource none run; splash at the box top (capture) |
| F7 | Amount 0 / enabled 0 / Panic | exact passthrough (diff 0) |
| F8 | cost (pane off, 120 pulls) | fx <= 3 ms at defaults and preset 5; state + water < 0.3 ms |
| F9 | demo: Masksource none / luma on the test clip | flowers bloom on still parts and scatter where the person moves (capture) |
| P1 | add pigment; td_errors | 4 passes compile; state 512 x 257 32F, splat / trail 540 x 960 16F; splat dispatch 32 x 32, clearoutputs on |
| P2 | freeze (Speed 0), read state twice 1 s apart | identical; trail unchanged (diff 0) |
| P3 | one-cook parity from a read state with `pigment_logic.state_step` | x within 1e-3 px for non-respawned particles; age += dts (1e-6) |
| P4 | splat at Quality 1, Size 1, Agefade 0 | lit texels = floor(x), floor(y) of live in-frame particles (exact set); untouched alpha 0 |
| P5 | trail max, Trail 1 | a pixel with no new dot decays exp(-dts) per cook (16F 2e-3) |
| P6 | points push / attract / swirl (Source demo, Pointforce 600, Radius 200, Flowstrength 0, 2 s) | density near a point < 30 % of mean (push), > 2x (attract), tangential speed > 0 (swirl) |
| P7 | mask attract (Fieldsource mask, Maskforce 300, Spawnmode mask) | > 90 % of particles in presence > 0.5 after 2 s; -300 empties it |
| P8 | Flowtop = BN_fluid2d/out2 (fluid running), Flowstrength 0 | particle velocity = Flowgain x field x 1920/342 within 5 % |
| P9 | Amount 0 / enabled 0 / Panic; cost (pane off, 120 pulls) | exact passthrough; <= 3 ms at Side 256 / Quality 0.5 (report Side 512) |
| V1 | add linevolume; td_errors | fx compiles (const arrays), 16 uniform blocks, 3 inputs |
| V2 | each preset frozen (`M['freeze'](I, t=1.0)`), Input black, Source demo, Masksource none; `linevolume_logic.pixel` at 300 sample points | within 3/255 at >= 97 %, median <= 0.004 |
| V3 | Amount 0 / enabled 0 / Panic | exact passthrough |
| V4 | Speed 0 then 2; Beatgain 1, Bpm 120, Kick 30 | rotation holds / advances 2 x Spin per s; kick once per beat |
| V5 | Follow 1, Source demo | the solid's lit-pixel centroid tracks point 0 within 2 % of H |
| V6 | cost per scene (pane off, 120 pulls) | <= 3 ms (aim ~1); preset 2 (Nest 4) separately |

## Verified live (26 Oct 2026, TD 2025.31550, build TD b4; 5-6 other TDs busy on the Mac)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Method: Speed 0 freezes (self-clocked state) then numpy references on readbacks in a later exec; one-cook parity =
`state_fb` + `state` read in one exec, the reference steps the first into the second; cost = `cost_start` /
`cost_read` (120 forced out1 pulls, T-102; per-op medians, the per-frame total is noisy under load); real fps =
an Execute DAT onFrameStart counter over 5 s (T-124 (4)). Pane on /project1/lab.

| # | Result |
|---|---|
| I1 / I2 | rack + 4 modules compile, td_errors clean; pts 16 x (x y vx vy), pts_tex 16 x 1, gi_mask 270 x 480, drive beats bpm level; second build 0 wires changed |
| I3 / I4 | demo: 16 present moving points; null pen1 (0.5625, -0.5) -> (1.0, 0.25); chop tx 0 ty 0.5 signed -> (0.5, 0.75); effectors (built on b4): sphere1 (0.28, 0.5) -> (0.75, 0.75), box1 -> (0.25, 0.25), Effselect box1 -> only box1. Face / mouse: not run live (no FT_face_track on b4; mouse needs a person) - offline tests only |
| I5 | gi_mask one-cook parity (Masksource luma, test clip): presence 4.9e-4, motion 2.3e-4 (16F) |
| R2 / R3 | ribbon segs vs numpy, presets 1-6 frozen: positions <= 0.023 px (float32; 3.7e-4 without strands), widths 1e-5, alpha 1e-6; chunk boxes 4e-4 px; out1 at 300 px (90-175 lit) within 2/255: 1.0 every preset |
| R5 | Amount 0 / enabled 0 / Panic: diff 0 |
| R6 | ribbon cost: default 1.82 total (fx 0.49 GPU after chunk boxes; 2.43 before), preset 6 2.6 (fx 1.24), preset 3 (4 x 7 strands, Subdiv 2) 3.09 (fx 1.74; was 4.77 at 6 ribbons x Subdiv 3) |
| F1 | flowers: state 128 x 8, water 128 x 20, inputs as designed, clean |
| F2 | one-cook parity: flowers exact (alive flags 448 / 448, pos 0.0, B 0.0); preset 5 pos 2.9e-5, water 2.1e-4 px |
| F4 / F5 | box mask (x 0.3-0.7): 53 of 53 living flowers inside presence after 3 s; moving the box: 33 scattering next read, 0 after Falltime, new ones at the new place |
| draw | flowers out1 vs `items` + `shade_grid` at 300 px: within 2/255 1.0 (237 items; and 1278 items with 17 scattering + water) |
| F8 | cost: meadow 230 flowers fx 1.57 GPU; dense frame-filling 356 (preset 7 on luma) fx 3.46 (6.3 before front-to-back early-out); preset 5 fx 1.5 |
| F9 | Masksource luma on the clip: flowers bloom on bright still areas, petals scatter over the moving person (capture) |
| P1 / P3 | pigment: state 512 x 257, splat / trail 540 x 960, dispatch 32 x 32, clearoutputs on; one-cook parity 65536 particles: respawn sets equal (246), max dx 1.3e-4 px, age exact |
| P4 | splat (Quality 0.5, Size 2 -> 1 px): lit set identical (50553 texels), colour 2.2e-4 median (16F) |
| P2 | freeze: state holds (only the meta cook counter moves); trail creeps up a little where dots overlap (last-write order varies per cook, max mode ratchets) |
| P6 | push: density near points 0.06 x mean; attract 2.55 x |
| P9 | cost default 1.76 total (fx 0.38, state 0.18, splat 0.07, trail 0.06 GPU) |
| V1 / V2 | linevolume: 16 blocks, 3 inputs, clean; presets 1-7 frozen (t 1, Input black, points static): within 3/255 1.0 at 300 px, median <= 0.0015 |
| V6 | cost fx GPU: wire 1.13 (2.19 before per-workgroup vertex projection), Nest 4 1.41 (3.69 before), hatch 0.51, relief 1.57, moire 0.49 |
| all | Amount 0 on every module and the rack: diff 0 |
| fps | b4 real fps: GEN_interactive parked 57.9-58.4; all four slots on (stacked) 50.3-54.3 (one 38.6 sample under a load spike) |

Live fixes: ribbon draw chunk boxes (`cbox` pass) + glow cut at 4.5 Glowwidth; flowers draw front-to-back with
per-pixel / per-tile early-out, per-item geometry once per tile, exact petal box skips; linevolume follow + vertex
projection once per workgroup; parity helpers clip 8-bit output and skip faded segments (T-123 (5)).
Captures (`output/`): `project1_lab_GEN_interactive_ribbon1_out1_2026-10-26T17-15-*.png` (presets 1-6),
`..._flowers1_out1_2026-10-26T17-29-27-774Z.png` (falls + blossoms), `..._flowers1_out1_2026-10-26T17-34-20-373Z.png`
(luma), `..._pigment1_out1_2026-10-26T17-38-25-105Z.png`, `..._linevolume1_out1_2026-10-26T17-41-*.png`.
b4 hung (0 % CPU, no reply) during a `td_layout check` of the rack right after these checks, while b2 was also hung
(T-148); the main session relaunched b4 from Build4.49.toe (all four modules); re-checked there (td_errors clean,
ribbons drawing), b4 saved Build4.52.toe.
- **Brought home** (`tools/bring_home.mjs`, lane entry removed first, T-138): main `/project1/lab/GEN_interactive`
  1473 ops = b4, errors 0, parked, main saved `JazibTD_home.426.toe` (b4 Build4.54.toe). Final rack: ribbon1 enabled
  (preset 1), flowers1 / pigment1 / linevolume1 enabled 0 (preset 1 each), Input auto, Source demo, Masksource none.

## Perf lane 2 (27 Oct, b2, 31550)
- **The rack's `pts` Script CHOP was the biggest cost of every module: 2.8-4.2 ms CPU per frame** (Source demo, 16
  points): `demo_points` called GEN_sim's numpy `hash3` 64 times per frame on scalars (~50 us each under Rosetta).
  Now the hashes are one vectorised call cached per (n, seed) and the wander noise is one vectorised call
  (`gen_interactive_logic._demo_hashes`); values are identical (offline test). In-TD paired timing: 9.3 -> 0.76 ms
  (lissajous + wander alternating); `pts` cook 0.28-0.40 ms.
- Module solo on b2 (own copy at /project1/perf2, pane elsewhere, loaded machine), whole COMP ms median before ->
  after: ribbon1 7.6 -> 3.7, flowers1 10.5 -> 6.3, pigment1 6.4 -> 3.2, linevolume1 8.0 -> 3.5. Left: flowers fx
  2.7 ms GPU (preset 1 meadow; the shader already culls per tile and stops front to back), CHOP to TOP `pts_tex`
  0.2-0.5.
- Home: main `gi_logic` text replaced from the builder file (un-parked first, T-146; `pts` 0 errors, 16 x 4,
  0.28 ms), parked, saved JazibTD_home.703; library GEN_interactive 0.2.1.

## Not done / open
- Hands: FT_face_track tracks faces only; hands come in as effectors (point sets / Nulls tagged `hands`) or any CHOP.
- Ribbon mirror / kaleido symmetry (needs per-tile mirrored culling) and text-as-SDF (FX5 E8 (d)) are not built.

## Lane F modules (27 Oct 2026, TD 2025.31550): strings (TC-28), parallax (SX-30 / 7C-31 / TC-05)
Added to `MODULES`; files `builders/gen_interactive_<m>.py`, `_logic.py`, `builders/glsl/gen_interactive_<m>*.glsl`,
`test/test_gen_interactive_<m>.py`; live checks in `builders/fx_track_checks.py` (`strings_parity`,
`strings_draw_parity`, `parallax_parity`).

### strings (FX7b TC-28 repelling strings, clean-room)
- `step` (K x (S + 1) rgba32f, Feedback `state_fb`): **one workgroup per string** (local size 256 = nodes), node
  offset + velocity px from the rest place; substeps <= `Substep` s inside one cook share offsets through shared
  memory + barriers (tension stays stable at high values). Acceleration = -Stiffness off + Tension (neighbour
  Laplacian) - Damping vel + Gravity + Wind (sin pattern) + rack points (push / pull / swirl within Radius, (1 - r /
  R)^2, x (1 + Audiogain level + Manual)) - Maskforce x grad(presence) (rack mask); `Kick` = an impulse across the
  strings once per beat; Pin top / both / none. Self-clocked meta row (T, last time, epoch, last beat): Speed 0 =
  frozen, a second cook in the same frame holds.
- `cbox` (ceil((K - 1) / 8) x S): a bounding box per chunk of 8 segments. `draw`: 8x8 tile lists of the chunks whose
  box (grown by the line + glow extent, glow cut at 6 Glowwidth) touches the tile (shared memory, <= 512 chunks per
  tile), capsules + glow per pixel, colour gs_pal(along / bend / index / speed + Flow x T). Strings pushed far from
  their rest place still draw whole (a fixed "reach" cut them: first live capture).
- Presets: 1 harp, 2 curtain (hanging, gravity + wind), 3 beat strum (Kick), 4 swirl threads (horizontal), 5 person
  repel (Maskforce: set the rack Masksource), 6 neon flow.
- **Verified live (b2):** physics one-cook parity (state_fb + step read together) pos **6e-5 px**, vel 2-4e-3 px/s,
  meta exact, with 16 demo points bending strings up to 200-400 px; draw parity over-tol **0** at 600-1000 px (8-bit
  out clipped like the GPU); Amount 0 / slot enabled 0 / Panic: diff **0**; presets 1-6 full state (Resetcount is a
  counter, not part of a look). Cost (pane off, 120 pulls): 3.3 ms total (draw 2.4 GPU, step 0.07, cbox 0.03) at 40 x
  64 under 5 busy TDs; Glow 0 1.5 ms; 12 strings 1.4 ms.
- **In main** (JazibTD_home.658): added by builder as `strings1` (enabled 0); physics parity 1.7e-4 px, draw over-tol
  0; GEN_interactive re-parked.

### parallax (FX7a SX-30 + FX7c 7C-31 + FX7b TC-05)
- One pass `fx` (in1, colour = `still` Movie File In filled to the slot size or the slot input, depth = `depthfile` or
  `Depthtop`): relief march from the near layer (t = 1) to the far one, sample uv - D(t), D(t) = O t + (uv - 0.5)
  Dolly t, first layer whose depth is >= t wins (correct occlusion), binary refine; O = Strength x (1 + Audiogain
  level) x (sway circle / side / up-down / figure 8 at Swayhz + Follow x the first rack point + Manual). Depth
  window Depthlo / Depthhi / Invert; fog to Colour A by (1 - depth); depth bands (TC-05: palette per band x luma).
  Zero offset and dolly 0 = the colour exactly.
- **Depth of a still is precomputed once outside TD** (plan default U3): `helpers/vision_bridge` kind 1 (Depth Anything
  V2 Small, Core ML, Apache-2.0) via `depth_socket_test.py` on one frame; demo pair `media/demo/parallax/`
  (webcam_ref frame 0 + its depth, SOURCES.md). Any live depth TOP (DC_depth_cam) works through Depthtop.
- Presets: 1 slow orbit, 2 side drift, 3 dolly breathe, 4 depth bands, 5 follow person, 6 stained glass.
- **Verified live (b2):** parity vs the reference at 500-800 px over-tol **0** (max 2-7e-3) for presets 1, 3 (dolly),
  4 (bands) and a two-layer test (a 0.3 x 0.2 white rectangle depth over black, Strength 0.12: the near rectangle
  slides over the far picture, 5.5 % of pixels changed); zero sway = in1 (diff **0**), Amount 0 diff 0; presets
  1-6 full state through the zkit panel. Cost 1.7 ms (fx 0.54 CPU + 0.83 GPU, 32 steps + 5 refine).

### skinner (FX7c 7C-25 Skinner shards on a performer; technique from Keijiro Takahashi's Skinner README, no code)
- `slots` (64 x (ceil(N / 64) + 1), Feedback `slots_fb`, self-clocked meta row: cook count, T, time, epoch): N points
  kept inside the rack mask (presence > Threshold; set the rack Masksource to `top` = CV_person_mask/out2, or `luma`);
  a point leaves -> 8 hashed tries for a new one; `Respawn` / s re-rolls kept points too.
- `tris` (128 x ceil(M / 64)): shard j re-rolls its 3 slots `Rerollhz` times / s (phase staggered), up to 6 hashed
  triples, kept when the longest edge is in Minlen..Maxlen px (Skinner's "long, large triangles"); shown with chance
  Density x (1 + Audiogain level + Manual) + Motiongain x the slots' mean motion; alpha = sin(pi x life fraction).
  Vertices follow the slots' current points (the shards stick to the body).
- `draw`: 8x8 tile lists of shard boxes, fill (inside distance, 1 px AA) + edge + glow (cut at 6 Glowwidth), the
  strongest shard colours the pixel (ties: lower index), gs_pal(per-shard hash), blended over the slot input.
- Presets: 1 glass shards, 2 needles, 3 solid facets, 4 motion burst, 5 slow crystal.
- **Verified live (b2, rack Input test + Masksource luma):** slots one-cook parity: valid set identical (512 / 512,
  0 mismatches), positions 5e-5 px (motion channel 2.4e-4, 16F mask); tris vs reference 5.4e-6; draw over-tol **0**
  at 300-400 px (preset 1 and 3); Amount 0 / slot enabled 0: diff **0**; presets 1-5 full state (zkit). Cost 2.1-2.2
  ms (draw 0.8-0.9 GPU, slots 0.07, tris 0.06).

**In main (lane F):** strings1 (JazibTD_home.658), parallax1 + skinner1 (.672) added by the builder one module per
exec, all enabled 0 (rest look unchanged); re-checked in main: parallax parity over-tol 0, skinner slots / tris /
draw parity (valid sets equal, draw over-tol 0); GEN_interactive re-parked; library `GEN_interactive` 0.2.0.

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.748).
