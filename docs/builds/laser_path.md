# laser_path: LP_laser_path laser path generator + beam preview (live v1 in main, 26 Oct 2026, no laser hardware)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

`/project1/lab/LP_laser_path`. Spec: `docs/research/BM_lasers.md` section 4 (clean-room, our own code). Any source
(test pattern / SOP / CHOP / POP / TOP trace / Text / audio scope) -> laser sample stream (`x y r g b i flag`) through
either the built-in **Laser CHOP** (Engine = Native, default) or our **numpy engine** (Engine = Own: draw order,
resample, corner dwell, 5-phase blanking, colour delay, frame budget), plus a beam-simulation preview and a stats table.
**No device output here** (that is LO_laser_out, spec section 5) and **no limits** (operator decides; interlock,
shutter and e-stop are the operator's). Nothing is routed to audio output.

**Status: BUILT LIVE v1 (26 Oct 2026, TD 2025.31550, Rosetta; no laser hardware).** `/project1/lab/LP_laser_path`,
backup `output/backups/LP_laser_path_build.tox`. Live facts: LEARNINGS T-85. Results (spec 4.9):

| # | Result |
|---|---|
| 1 | laserCHOP, laserdeviceCHOP, etherdreamDAT, inPOP, poptoCHOP, traceSOP, textSOP all create; builder `missing` = [] after 2 name fixes (Text SOP closedpolys, POP-to attribscope string) |
| 2a | Own, square: 341 samples @ 48000, 20 flag==1 in 4 runs, corners 4, budget 800, overflow 0.4263, est_flicker_hz 140.762 (exact, after the float32 fix) |
| 2b/3 | Native: 800 samples per cook (time slice), channels x y r g b debug; image 117 samples (Native step ~4x ours at the same Stepsize: 21 per 1.6 edge at 0.02), 4 hold samples per corner (ours 5), 12 blank per image (ours 0). Documented difference |
| 4 | dashed 50: none 42.348 / 1003 / 3 frames, nearest 9.172 / 668, twoopt 8.424 / 660 / 2 frames (80% shorter): exact |
| 5a | corners mean 485-515 vs edge midpoints 68 (PNG, 0..765 scale): dwell glow ok. Beam reads as dots (spot core < 10.8 px sample spacing): open |
| 5b | Showlag, Galvobw 1500: lit px outside bbox 115 / 101 / 98 / 70 at Colordelay 0 / 0.05 / 0.1 / 0.2 ms: falls monotonically (positive delay helps) |
| 7 | BPM 120, Beatdiv 1: 25 samples all match on iff absTime mod 0.5 < 0.25 (2 Hz) |
| 8 | stored clip: 10-13 shapes, 1614-1750 samples (+-4%), but ~21 ms CPU per cook: over budget (preview/test source only) |
| ILDA | Exportilda pulse -> `output/laser/LP_laser_path.ild` + `_ilda.json`: square 341 pts 2792 B, dashes 660 pts / 410 blanked, read back exact (xy <= 1/32767), Ether Dream 18 B/pt, LaserCube <= 140 pts/datagram: ok |
| perf | static image: 1 cook per change, 0 ms/frame CPU after the absTime fix; preview GPU ~1.7 ms when viewed (glow_blur 1.0); wall fps 58-59 with other lanes running |
| layout | ok except one reported back wire persist_fb -> persist_decay (Feedback `top` ref counted as an edge; handlers fix, T-85) |

Everything marked **LIVE CHECK** below was the prep's open list; the table above answers it.

In: `in1` In SOP, `in2` In CHOP (`x y [r g b id lascorner]`), `in3` In TOP (trace), `in4` In POP. Out (output only):
`out1` Out CHOP = `laser` (x y r g b i flag, sample rate = Pps), `out2` Out TOP = `preview` (Previewres square,
default 1080x1080: a tool picture, not a look, so the 1080x1920 look rule does not apply), `out3` Out DAT = `stats`.

## Files
| File | What |
|---|---|
| `builders/laser_path_logic.py` | pure logic, no `td` (copied into `lp_logic`): shapes, transform/warp, nearest + 2-opt order, resample, corner dwell, blanking phases, colour delay, budget/overflow, drive, galvo model, dwell weights, patterns, ILDA f5 write/read, EtherDream/LaserCube packers |
| `builders/laser_path_rt.py` | TD runtime (copied into `lp_rt`): sources -> rows, Native/Own cooks, drive, preview points, stats, Savesnap |
| `builders/glsl/laser_path_sprite.glsl` | the only shader: soft spot, single pass, no inputs (T-46 n/a), copied into `sprite_pixel` |
| `builders/laser_path.py` | idempotent builder `build(parent_path='/project1/lab')` |
| `test/test_laser_path.py` | 49 offline tests: `python3 -I -m unittest discover -s test -p 'test_laser_path.py'` |

## Build (~15 min including checks)
0. `td_guide`, `td_status`. Check `logs/exec.log` for which COMPs other lanes touch (never park theirs). Watchdog
   running (T-77). Network pane may stay where it is: the builder never moves it.
1. Probe first (one call, scratch COMP, spec 4.9 step 1; **LIVE CHECK**):
   ```python
   s = op('/project1/lab').create(baseCOMP, '_lp_probe'); r = {}
   for cls in ('laserCHOP', 'laserdeviceCHOP', 'etherdreamDAT', 'inPOP', 'poptoCHOP', 'traceSOP', 'textSOP'):
       try:
           o = s.create(globals()[cls]); r[cls] = [o.errors(), [p.name for p in o.pars() if p.page is not None][:60]]
       except Exception as e:
           r[cls] = 'ERR %s' % e
   result = r
   ```
   Then `safe_destroy(op('/project1/lab/_lp_probe'))` in a second call. Record the Laser CHOP par names (outputrate,
   stepsize, bstepsize, mincornerhold, maxcornerhold, closedoverlap, preblankon/off, postblankon/off, colordelay,
   interpcolors, source, chop, timeslice, debug par) in LEARNINGS (T-nn) whatever the outcome. If `laserCHOP` fails
   on this Mac: build anyway (the builder survives it: `missing` lists it), set `Engine = own` as the COMP default,
   note `available:false` for Native in LEARNINGS + `docs/FUTURE.md`.
2. Build (one structural call, T-31):
   ```python
   ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/laser_path.py').read(), ns)
   result = ns['build']('/project1/lab')
   ```
   Read `result['missing']`: every entry is a par/op name this build lacks (e.g. `geo.instancecolorop`,
   `beam_mat.srcblend=one (menu [...])`). Fix the name in the builder from the printed menu/par list and rebuild
   (idempotent: ops reused by name, par values kept). `result['laser_pars']` = the Laser CHOP's real par names.
3. `td_errors /project1/lab/LP_laser_path` (includes Script errors, T-55); `td_layout check` -> ok (stages: Controls,
   0 Code, 1 Source, 2 Native engine, 3 Own engine, 4 Drive + out, 5 Beam preview).
4. Save: `td_save_project` + `td_tox_save` of the COMP to `output/backups/LP_laser_path_build.tox` (spec 4.7).

Crash rules honoured by the builder: T-67 (only a plain bool in storage: `lp_fps_bound`), T-70 (`_sd` =
safe_destroy, own `controls_window` closed before a rebuild, zkit refreshes the panel in place, pane never moved),
T-74/T-76 (no `numpyArray` / `evalTextSize` / force-cook anywhere in builder or runtime), T-64 (`Fps` only READS
`project.cookRate`), T-46 (one single-pass GLSL TOP with no inputs; preview chain = stock Render/Feedback/Level/
Composite/Blur). The offline tests check these statically (`BuilderSafety`).

## Network (stages)
- **Controls**: zkit `controls` + `controls_window` (pages Source, Path, Shape, Drive, Preview), `controls_open`
  Parameter Execute (Opencontrols, Savesnap -> `output/laser/LP_laser_path.json`).
- **0 Code**: `lp_logic`, `lp_rt`, `warptable` (3x3 grid, identity; Warp toggle uses it).
- **1 Source**: `in1..in4`; trace chain `trace_clip` (stored `media/webcam/webcam_ref_5s.mp4`, plays only while
  Source = toptrace + Tracesrc = clip) / `in3` -> `trace_src` -> `trace_res` -> `trace_blur` -> `trace_mono` ->
  `trace` (Trace SOP); `text_sop`; `pop_chop`; `rows` Script CHOP (one sample per vertex: x y r g b id lascorner).
- **2 Native engine**: `native_in` (transform, tint, draw order; ids renumbered in draw order) -> `laser_native`
  (Laser CHOP, every timing par bound to the COMP pars) -> `native_fix` (-> x y r g b i flag).
- **3 Own engine**: `own` Script CHOP (`lp_logic.run_engine`) ; `engine` Switch (Engine menu).
- **4 Drive + out**: `drive` (Intensitysrc manual/BPM/audio/CHOP, Strobe, Blackout, Hold) -> `laser` Null -> `out1`;
  `stats` Script DAT -> `out3`.
- **5 Beam preview**: `preview_pts` (galvo lag when Showlag, dwell weights, this frame's window when the image needs
  > 1 frame) -> `beam_geo` instanced `spot` rectangles, `beam_mat` Constant MAT additive with `sprite` -> `beam_render`
  (ortho cam, width 2) -> `persist_fb` / `persist_add` (one pixel GLSL pass: render + feedback x decay, half life
  Persist ms) -> `glow_blur` -> `preview_comp` (one compute pass: persistence + glow + Bg colour) -> `preview` -> `out2`.

Cooking: Script CHOPs cook only when what they read changes, except via their `Frame` clock par: `rows` every frame
for audio / toptrace / calib pattern, `drive` while BPM/audio/CHOP/strobe/calib is on, `preview_pts` while the image
needs more than one frame. **LIVE CHECK:** a Script CHOP that reads COMP pars and other ops' data inside onCook
recooks when they change (TD dependency tracking); if not, the stream freezes after a par change: then add those
pars to the clock expression.

## Live verification (spec 4.9; name the build: TD 2025.31550; no hardware)
Un-park only LP_laser_path; leave other lanes' COMPs alone. Set pars with `td_set_pars`; read `stats` with
`td_get`/`td_exec` (`[[c.val for c in r] for r in op('.../stats').rows()]`); read the stream with
`op('.../laser')['x'].vals` etc. Read TOP pixels only with `td_inspect` / in a later call, >= 2 frames after any
par change (T-74).

| # | Set | Expect (offline numbers from the same logic) |
|---|---|---|
| 1 | probe above | the 3 laser ops create with no "not supported" error (**LIVE CHECK**) |
| 2a | Engine=own, Source=pattern, Pattern=square, Size=0.8, Pps=48000, Fps=60, Stepsize=0.02, Minhold=0.1, Maxhold=0.1, Holdadd=0, Colordelay=0 | `laser` sample rate 48000, **341 samples** (1 start + 4x80 edge + 4x5 corner hold), stats: points_total 341, points_blank 0, corners 4, frame_budget 800, frames_per_image 1, overflow 0.4263, est_flicker_hz 140.762; flag==1 count 20, 4 runs |
| 2b | same, Engine=native | `laser` sample rate 48000 (`td_get` Info / `laser.rate`); **LIVE CHECK** sample count: 800 per frame if the Laser CHOP time-slices (spec), else its own image length; `flag` channel exists only if the debug par was found (`result['missing']`) |
| 3 | 2a vs 2b | corner-hold samples and blank counts Native vs Own within +-2 samples; a larger gap is a documented difference (record both numbers), not a failure. **LIVE CHECK:** Native's hold unit (ms vs samples vs factor) |
| 4 | Engine=own, Pattern=dashed, Count=50 (seed 7), default Path pars (Pps 30000, Fps 60) | Order=none: blank_travel **42.348**; Order=nearest 9.172; Order=twoopt **8.424** (80% shorter; spec asks >= 20%). twoopt: points_total 660, frames_per_image 2; none: 1003, 3 |
| 5a | Pattern=square, Showlag=0, Previewon=1 | `td_inspect out2` non-black; mean of the 4 corner pixels > mean of the 4 edge midpoints (dwell glow). Pixel coords: square spans +-0.8 -> px (0.1..0.9) x Previewres |
| 5b | Showlag=1, Galvobw=1500, Colordelay=0 | rounded corners + tails: lit pixels outside the square's bbox > 0; raising Colordelay (0.05, 0.1, 0.2 ms) -> that count falls monotonically (**LIVE CHECK**: sign of the useful delay) |
| 6 | Fake DAC | not in this COMP (LO_laser_out); skip |
| 7 | Intensitysrc=bpm, Bpm=120, Beatdiv=1 | `laser` `i` (and r g b) toggles at 2 Hz: 0.25 s on / 0.25 s off (+-1 frame); record over 2 s with a per-frame Execute DAT, remove it after |
| 8 | Source=toptrace, Tracesrc=clip | stats.shapes > 0; points_total stable within +-15% over the 5 s loop. **LIVE CHECK:** Trace SOP par names (`top`, `thresh`, `step`), prims/points/`closed` API used by `_sop_rows` |
| 9 | all | `td_errors` clean after every step; `td_layout check` ok |

Extra checks worth one call each: Text source (Text SOP outline output + Font par expr: **LIVE CHECK**, missing ->
listed); Warp=1 with the identity warptable = no change in `laser` x/y; Blackout=1 -> r g b i all 0, x y unchanged;
Hold=1 freezes the stream; Savesnap writes `output/laser/LP_laser_path.json`.

## Perf / fps target
Project stays at **60 fps** (cookRate untouched), COMP **<= 3 ms** per frame in steady state. Report with the other
lab COMPs parked, pane location noted (T-73): `td_perf` on the COMP + real fps (wall clock between frame starts).
Offline CPython (native arm64, so TD's Rosetta Python will be slower, **LIVE CHECK**): Own engine square 0.6 ms,
star 636 samples 1.0 ms, 50 dashes + twoopt ~7 ms, 300 dashes + twoopt ~23 ms (2-opt budget Orderms counts
moves: 1e4 per ms); galvo filter (Showlag) ~1 ms per 640 samples (Python biquad loop). Static patterns cook once,
so these costs only hit on a change; every-frame sources (audio, trace, calib) with many shapes are the risk: lower
Count / Orderms or use Native. Preview (1080 px Render + Feedback + Blur): target < 2 ms GPU (**LIVE CHECK**,
td_perf has no GPU time, T-42: use the ops' `gpuCookTime`). If fps drops, Previewon=0 stops the Render TOP.

## LIVE CHECK list (TD facts not confirmed on this Mac)
1. `laserCHOP`, `laserdeviceCHOP`, `etherdreamDAT` create and cook under Rosetta (31550).
2. Laser CHOP par names + menu values: `source`=chop, `chop` (by name 'native_in'), outputrate, stepsize, bstepsize,
   mincornerhold, maxcornerhold, closedoverlap, preblankon/off, postblankon/off, colordelay, interpcolors; units of
   the hold pars; whether a debug/flag channel needs a toggle (builder tries `debug`/`debugchan` toggles).
3. Laser CHOP output length per cook (time-slice, 800 per frame at 48000/60) and the channel names it emits
   (`x y r g b` + intensity/debug names); `native_fix` maps `i`, `debug`/`flag`/`debugchan`.
4. `inPOP` and `poptoCHOP` (par `pop`, `attribscope`) and their channel names for P / Color (`_pop_rows` tries
   P(0)/P0/Px/tx...).
5. Trace SOP pars `top`, `thresh`, `step`; Text SOP `output` outline menu + `font` par; SOP Python API
   (`prims`, `pr.closed`, `v.point.P`, `Cd`).
6. Geometry COMP instancing pars: `instancing`, `instanceop`, `instancetx/ty`, `instancer/g/b`, `instancecolorop`,
   `instancecolormode`=replace; Constant MAT `blending`, `srcblend`/`destblend`=one, `depthtest`, `depthwriting`,
   `postmultalpha`; Render TOP `render`, `antialias`; format menu `rgba16float` on GLSL/Render/Composite TOPs.
7. Script CHOP dependency tracking on COMP pars and other ops read in onCook (else extend the clock expressions).
8. Feedback persistence (Feedback TOP `top` = persist_add) shows no tearing on this Mac (stock ops, but feedback
   amplifies T-46-type faults): watch `preview` for 10 s.
9. Rosetta Python cost of the Own engine and the galvo biquad (stats `own_ms`, `preview_ms`).
10. Movie File In of `media/webcam/webcam_ref_5s.mp4` exists on disk (git-ignored) and loops.
11. Sign/size of a useful Colordelay in the preview (5b).

## Perf lane 2 (27 Oct, b2, 31550)
- The three per-frame Script CHOPs (native_fix, drive, preview_pts) moved channel data through Python lists
  (`.vals`, list comprehensions): 0.79-0.89 ms CPU each with the 500-sample square. `laser_path_rt` now reads channels
  as numpy arrays (`_arr`) and writes them with `copyNumpyArray` (float32): 2.49 -> 0.93 ms CPU for the three (b2,
  pane elsewhere). Stored samples equal the old path exactly (offline test `RtChannelIO`, run with `LP_RT_OLD`).
- Left: the beam preview chain (persist_decay Level, glow_blur, preview_comp, persist_add) ~2-2.6 ms GPU at 1080x1920
  and beam_render ~0.9 ms CPU; a fused GLSL preview would cut it but changes the Blur TOP look (not done).
- Home: main LP_laser_path rebuilt by builder (0 errors, Engine own there), parked, saved JazibTD_home.720; library 0.2.0.

## Perf wave 3 (27 Oct, b2 -> main, 31550)
- Preview chain merged: `persist_decay` Level + `persist_add` Composite -> one pixel-mode GLSL `persist_add`
  (`glsl/laser_path_persist.glsl`); the 3-input add Composite + the `bg` Constant -> one compute `preview_comp`
  (`glsl/laser_path_look.glsl`, background keeps the 8-bit steps). The Blur TOP stays (same glow). persist_add is
  pixel mode because the Blur reading a compute output cost ~2x (T-222).
- Parity vs the old chain (saved pars, static image, converged): out2 rgb mean 2e-5, p99.9 0.0039, max 0.047 at
  peaks ~10 (16F rounding order); look pass alone bit-exact. Alpha still accumulates without decay, as before.
- b2 (load 25-36): 2.86 -> 2.1-2.6 ms, 60 fps (main final 5.66 was at higher load). Left: glow_blur 0.4-0.7 GPU,
  beam_render 0.55 (Render TOP floor, T-198), persist_add 0.2-0.5.

## Not done / open
- Section 5 (LO_laser_out: Laser Device CHOP wrapper, LaserCube UDP, ILDA recorder, fake DACs `test/fake_dacs.py`).
  The packers it needs are already in `laser_path_logic` and tested (ILDA f5 round trip, EtherDream 18/20-byte
  structs, LaserCube 140-point datagrams + info parse).
- MCP typed tools of spec section 6 (`td_laser_probe`, ...): add when a lane needs them (docs/EVOLVING.md).
- Preview haze/volumetric fan; ILDA import view.
