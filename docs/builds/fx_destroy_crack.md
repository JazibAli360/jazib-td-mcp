# fx_destroy_crack: FX_destroy module `crack` (26 Oct 2026, TD 2025.31550; offline prep, then live on scratch + main)

Glass crack, broken LCD, dead pixels and stuck lines (FX1 DG-16, FX4 D5, FX0 backlog #45). This is a module of the
`FX_destroy` rack (`builders/fx_destroy.py`, same lean slot rack as `docs/builds/fx_glitch.md`: slot = module COMP +
Cross + Switch, zkit controls, presets, Panic). Nothing in the rack changes: the rack finds the module by name.
Live results: section "Verified live" (all C1-C10 ran; the **LIVE CHECK** notes in the table are answered there).

Files: `builders/fx_destroy_crack.py` (PAGES, PRESETS, shaders, `build(m, H)`), `builders/fx_destroy_crack_logic.py`
(numpy reference + hits state mirror + CLI for the live checks), `test/test_fx_destroy_crack.py` (21 offline tests,
glslc compile of both shaders against TD stubs):
`python3 -I -m unittest discover -s test -p 'test_fx_destroy_crack.py'`.

## Build (td_exec, main TD after FX_destroy exists)
```python
ns = dict(globals()); exec(open('<repo>/builders/fx_destroy.py').read(), ns)
ns['add']('/project1/lab/FX_destroy', 'crack')        # crack1, wired last, zkit panel + 5 presets
ns['remove']('/project1/lab/FX_destroy', 'crack1')     # if needed
```

## Network (inside crack1)
| Stage | Ops |
|---|---|
| 1 In | `in1`, `pulse_exec` (Trigger / Reset -> Hittime / Resettime, rack helper), `beat_exec` (Beat CHOP rising edge -> Hittime), `idle` (1x1 Constant) |
| 2 Crack | `hits` (compute, 9x1 rgba32float, readwrite in place, no inputs), `hit_sel` (Switch: idle while Source = point, so `hits` is not pulled), `fx` (compute 8x8, format useinput, in0 picture, in1 hit_sel) |
| 3 Out | `out1` |

`hits` texels 0..7 = hit x px, y px, trigger time (-1 = empty), hit number; texel 8 = seen trigger time, hits so far,
7.0 (initialised marker), last cook time. A fresh texture (no marker) or a Reset newer than the last cook empties it
and records the current trigger time as seen, so an old Trigger is never replayed. One new hit per cook, stored in a
ring of `Maxhits`; position = Point/Effector, moved toward a hashed random frame position by `Scatter`.

`fx` is the whole look in ONE compute pass (T-46/T-47), 16x16 workgroups. Per workgroup it first puts the impacts, up to 8 x 32 bleed
bars and 64 stuck lines in shared memory (two `barrier()`s), then per pixel:
1. **Glass** (per impact within reach): log-polar Voronoi around the impact, `u = (angle + pi) * Radials / 2pi`,
   `v = ln(r) * Rings`, so cells are radial wedges that shrink as 1/r (spokes + rings, denser at the impact). Line =
   distance to the bisector of the 8 neighbours of the nearest cell, converted to screen px with the log-polar
   Jacobian (`e_px = e * r / sqrt((a n_u)^2 + (b n_v)^2)`), with width `Crackwidth` tapering outward. Every edge has
   its own reach `Radius * (0.55 .. 1.15)` (jagged front) and ring edges are kept with probability `Ringcracks`. The
   angle wraps (cell index mod Radials). `Detail` adds a second layer (2.3x spokes, 2x rings, half width, 0.6 reach).
   `Core` px = crushed sparkle + strong jitter at the impact. Pieces (cells with seed radius < 0.9 R) get a small
   offset (`Refract`/2, falling off outward) and `Tint`; the line bends the picture along its normal (`Refract`);
   `Chips` = share of pieces near the impact that fall out to `Back` (black or alpha 0).
2. **Ink** (`Ink` x height): fbm-edged blot, black core, spectral halo (`Inkhue`). Grows as sqrt over ~3/Speed s.
3. **Bleed bars** (`Bars` per hit): 1..`Barwidth` px coloured bars (R G B C M Y W), centred on the impact +-
   `Barspread`/2 x width, extent growing with the crack; vertical, horizontal or both.
4. **Stuck lines** (`Lines`, global, seed-placed, exact px): black, a colour, or a smeared pixel (one picture texel
   repeated down/along the line). `Linewidth` px.
5. **Dead pixels**: cells of `Cluster` px are dead with probability `Dead`; inside, each pixel with `Clusterfill`;
   `Deadlit` share of clusters are stuck on (R, G, B or W) instead of black.
`Flicker` Hz blinks bars + stuck lines (hashed per period, 70 % on). No limiter (user rule).

Amount 0 = texelFetch passthrough (whole dispatch). Pixels no part touches are written from `texelFetch` too, so
outside every effect the output is bit-exact. `View` = map outputs r = line strength, g = chip, b = piece hash (0
outside the cracked area), a = 1, for the numpy parity check (and usable as a matte).

Source **point**: one crack at the Point / Effector Null, live (follow the Null), size = `Radius` (animate it to
grow). Source **hits**: Trigger pulse, Beat CHOP (rising edge) or `Auto` s each add a hit that grows with
`ease3(age * Speed)` and fades to nothing over `Fade` s (0 = stays until Reset or replaced).

## Pars
Crack page: Amount, Source, Trigger, Reset, Auto, Beatchop, Maxhits (1-8), Scatter, Speed, Fade, Radius (x height),
Radials, Rings, Ringcracks, Jitter, Wobble px, Detail, Core px, Crackwidth px, Crackglow, Crackdark, Refract px,
Tint, Chips, Back, View, Seed. LCD page: Ink, Inkhue, Bars, Bardir, Barwidth, Barspread, Baropacity, Lines, Linedir,
Linewidth, Dead, Cluster, Clusterfill, Deadlit, Flicker. Colours: Crackcolor. Shared: Point page (Effector, Pointu,
Pointv), State page (Resettime, Hittime). Slider ranges only, no clamps. Defaults = glass only (all LCD parts 0).

Presets (zkit, seeded once): 1 dropped phone, 2 bullet hole, 3 broken LCD (dark lines + ink + bars + stuck lines),
4 dead LED wall (no glass: stuck lines + dead clusters + flicker 6 Hz), 5 beat cracks (Source hits, Auto 1 s,
Scatter 0.8, Fade 4 s, 4 hits, Radius 0.38, Detail 0: cost, see Verified live).

## Offline results (this prep)
- 21 tests pass; both shaders compile with glslc (OpenGL target, TD stubs). glslc is a syntax/type check, not a TD
  compile.
- Reference crack maps (1080x1920, impact at Point 0.5 / 0.5, `crack_map`): preset 1 line>0 0.0615 of pixels,
  line>0.5 0.0219, chip 0.0394, cell>0 1.0000; preset 2 line>0 0.0312, chip 0.0329, cell>0 0.4956; preset 3 line>0
  0.0148, cell>0 0.2564. Wobble on/off changes these by < 0.001. A preview of presets 1-3 looked like radial glass
  cracks with fine branches and a crushed core (scratch render, not kept).
- Exact LCD numbers, preset 4 (Flicker 0, seed 4, 1080x1920): dead_px 4753, line_px 17964, lcd_px 22672. The 12 stuck
  lines (axis 0 = vertical at column x, 1 = horizontal at row y; kind 0 black, 1-7 colour, 8 smear):
  (0, 1047, 3) (1, 1038, 8) (0, 589, 1) (1, 334, 6) (0, 713, 2) (1, 433, 5) (0, 377, 3) (1, 1218, 2) (0, 153, 7)
  (1, 672, 6) (0, 188, 2) (1, 207, 1). Print again: `python3 -I builders/fx_destroy_crack_logic.py expect`.

## LIVE CHECKS (about 15 min; FX_destroy un-parked, clip paused, each read 4+ frames after a change, one TOP
readback per exec, T-74)
Save readbacks outside TD and compare with the CLI, not inside TD (the numpy reference takes 3-4 s per 1080x1920
map): `np.save('<repo>/output/crack_out.npy', op('<crack1>/out1').numpyArray(delayed=False))`, then
`python3 -I builders/fx_destroy_crack_logic.py map output/crack_out.npy 1`.

| # | Check | Expected |
|---|---|---|
| C1 | `add` crack -> `td_errors` on crack1, `fx` / `hits` GLSL info | 0 errors / warnings; panel + 5 presets in `controls/zk_presets`; `td_layout check` ok. **LIVE CHECK**: shared memory of ~9.3 KB (sBa + sBb + sLn + sH) is accepted by MoltenVK |
| C2 | Passthrough: Amount 0; slot enabled 0; mix 0; Panic on (preset 1); also Amount 1 with Radius 0 and all LCD parts 0 | numpy max abs diff img_src vs out1 = 0 in all five. Control: preset 1 diff > 0 |
| C3 | Map parity: preset 1, View map, Point 0.5/0.5, save out1, CLI `map ... 1`; then preset 2 (`map ... 2`) | got>0 near ref>0 (preset 1 line 0.0615 / chip 0.0394 / cell 1.0; preset 2 0.0312 / 0.0329 / 0.4956); `|d|>0.1` under 1 % per channel (only near-tie cell borders, float32 atan/log). **LIVE CHECK**: numpyArray row 0 = texel y 0 (bottom). If the fractions match but `|d|>0.1` is ~10 %+, rows are flipped: compare with `[::-1]` and record a T-nn |
| C4 | LCD exact: preset 4, Flicker 0; save img_src and out1 in two execs (clip paused), CLI `lcd in.npy out.npy 4` | max abs diff <= 1/255 (8-bit quantisation only), 0 px over; changed px <= lcd_px 22672 (a stuck colour can equal the picture); a vertical line at x 1047-1049 and a horizontal one at row 1038 |
| C5 | Hits: Source hits, Maxhits 4, Scatter 0; read `hits` (9x1 float) right after the first cook; 6 Trigger pulses in separate execs ~0.3 s apart; then Reset | first read: texel 8 = (Hittime, 0, 7, ~now), every z = -1 (no replay; **LIVE CHECK** fresh readwrite texture has no marker). After 6: count 6, texel numbers [5, 6, 3, 4], x/y = Point px (540, 960). Reset: count 0, all z = -1. **LIVE CHECK**: `hit_sel` is 9x1 while Source = hits (Switch takes the selected input's size) |
| C6 | Growth + beat: one Trigger, map view, line>0 share at ~0.05 / 0.25 / 1 s; Fade 2; then Beatchop = a 2 Hz square LFO; Auto 1 | share rises then holds (Speed 4: full by 0.25 s); with Fade 2 out1 = img_src (diff 0) after 2 s; beat -> count +2/s; Auto 1 -> +1/s |
| C7 | Effector: Point page Effector = a Null, tx 0.2 ty -0.1 | impact (crushed core, brightest blob in map r) at about (756, 768) px |
| C8 | Cost: per preset, out1 pulled per frame, 120 frames, median gpu+cpu of fx + hits; project fps over 300 frames with the rest parked | target <= 3 ms each and project 60 fps (cookRate untouched). Expect preset 1 (full-frame glass + Detail) highest: if over 3 ms, Detail 0 removes the second layer (about 40 % of the glass cost); preset 5 = up to 6 overlapping hits. Report the numbers |
| C9 | Presets: zkit Recall 1-5 | pars exactly as stored; one capture of preset 1 and one of preset 3 on the test clip |
| C10 | Wrap-up | `td_errors` clean, `td_layout` flow, `td_checkpoint`, save, park FX_destroy (unless another lane is on it), results + cook ms + fps into this doc and LEARNINGS (T-nn) |

## Verified live (26 Oct, 31550; scratch first, then main with the FX_glitch / FX_analog lanes cooking)
- **C1** `add` -> crack1 (7 wires), 0 errors / warnings, compute "Compiled Successfully" (the ~9.3 KB shared memory is
  accepted by MoltenVK), 5 presets in `controls/zk_presets`, `td_layout check` ok (rack + module).
- **C2 passthrough** (img_src vs out1, clip paused, separate execs, read 12 frames after each change): Amount 0 -> 0;
  slot enabled 0 -> 0; mix 0 -> 0; Panic on -> 0; Amount 1 + Radius 0 + LCD parts 0 -> 0 (re-run after the
  optimisation: 0). Control preset 1: max 0.96, 89 % px changed.
- **C3 map parity** (Point 0.5 / 0.5): preset 1 line 0.0613 (ref 0.0615) / chip 0.0394 / cell 1.0, preset 2 0.0311 /
  0.0329 / 0.4956; `|d|>0.1` 0.0000 % on every channel. numpyArray row 0 = texel y 0 (no flip). Same numbers after the
  optimisation.
- **C4 LCD exact** (preset 4, Flicker 0): max |d| 0.00000, 0 px over 1/255, changed px 22624 = reference 22624 (the
  prep's 22672 counts px whose stuck colour equals the picture); column 1047 and row 1038 fully changed.
- **C5 hits** (Maxhits 4, Scatter 0): first read texel 8 = (-1, 0, 7, now), all z = -1 (fresh readwrite texture has no
  marker, no replay); `hit_sel` is 9x1. After 6 Trigger pulses (18 frames apart): count 6, numbers [5, 6, 3, 4], x/y
  (540, 960). Reset: count 0, all z = -1.
- **C6** one Trigger, Speed 4: line share 0.013 at 0.02 s, 0.0617 at 0.22 s, 0.0617 at 1 s / 1.9 s; Fade 2: out1 =
  img_src (diff 0) 3.3 s after the hit; Beat CHOP = 2 Hz square LFO: +7 hits in 3.4 s (2.06/s); Auto 1: +5 in 5.8 s.
- **C7** Effector Null tx 0.2 ty -0.1: brightest map block at (762, 760) px (expected 756, 768).
- **C8 cost.** First version on main (median cpu+gpu of fx + hits per pulled frame): preset 1 8.6 ms, 2 6.5, 3 6.5,
  4 5.6, 5 21.6 (GPU 34 ms at one point). Fixed without changing a pixel (C2-C4 identical after): 16x16 workgroups
  (the 8x8 groups each rebuilt 256 bars + 64 lines in 9.3 KB shared memory -> low occupancy, 4x the setup work),
  bars loop over the used bars only (was `nh * 32` shared reads per pixel even with Bars 0), the 3x3 cell seeds cached
  and reused by the edge loop, an exact early skip of edges farther than the widest crack (before the pair hashes),
  and the Detail layer only inside its 0.69 R reach. After (main, other lanes on the GPU, so +-50 %): preset 1
  4.0 ms (p90 5.4), 2 3.5, 3 6.4 on main / 1.8-2.4 GPU on scratch, 4 1.85, 5 steady 5.3 with 4 live hits (was 6 hits
  -> preset 5 now Maxhits 4, Fade 4, Radius 0.38, Detail 0). Cost scales with the summed area of live hits (each hit
  = its own glass layer): Detail 0 and a smaller Radius are the dials. td_watch with preset 1 and the clip playing:
  58.8 fps avg (absTime), 51.5 real cooks/s with the test clip decode at 5.9 ms/cook, fx ~3.2 ms per cook;
  cookRate 60 untouched.
- **C9** zkit Recall 1-5: every stored par exact. The first Recall right after the module rebuild missed (slot 2),
  the retry and all later ones were exact. Capture (preset 3, Point 0.45 / 0.6):
  `output/project1_lab_FX_destroy_crack1_out1_2026-10-26T15-06-18-793Z.png`.
- **C10** `td_errors` clean, layout ok, checkpoint `output/checkpoints/FX_destroy/FX_destroy_20261026-200641.tox`,
  project saved (.280), FX_destroy parked; all four slots left enabled (crack1 on preset 1).

## Not done / open
- Preset 1 (full-frame glass + Detail) sits at ~3-4 ms and multi-hit looks at ~5 ms on this Mac: a further cut needs
  a look change (e.g. one shared wobble field, or later hits' cracks stopping at older ones), not done.
- `BEAT_EXEC` is a copy of shatter's (two modules use it now): the FX_destroy lane may move it into the rack's `H`.
- No Mask page (DG-16 does not need one yet). No cabinet-aware dead modules (that is DG-28 `FX_ledfail`).
- The ink halo and bar colours are fixed palettes (spectral cos palette / 7 primaries); a colour page only if asked.
