# fx_analog_crt: FX_analog modules `crt` (+ `monitor` presets) and `crtfault` (offline prep, 26 Oct 2026)

**Status: offline prep only. TD has not been touched.** Every claim below that needs TD is marked **LIVE CHECK**. A live
lane builds both modules and verifies them with the checks in this file (target about 15 minutes). Target build: TD
2025.31550.

| File | What |
|---|---|
| `builders/fx_analog_crt.py` | Module `crt`: PAGES (JZB_Lofi_CRT names), 8 zkit PRESETS, three compute shaders, `build(m, H)` |
| `builders/fx_analog_crtfault.py` | Module `crtfault`: PAGES, 5 PRESETS, one compute shader, `build(m, H)` |
| `builders/fx_analog_crt_logic.py` | Pure maths shared by both modules: raster, mask, warp, flicker, roll lock-in, Degauss, power, `clock_step`, the 13 MONITORS, numpy references `crt_ref` / `fault_ref`, the shared GLSL lib, clock / pulse callback texts, `save_snippet` + `check_dir` (CLI) |
| `test/test_fx_analog_crt.py` | 28 offline tests: `python3 -I -m unittest discover -s test -p 'test_fx_analog_crt.py'` (glslc compile included) |

The rack is the FX_analog rack (`builders/fx_analog.py`, from the ntsc lane; the FX_glitch rack reused). The rack finds
a module by its file name `fx_analog_<module>.py`, so these two modules need no rack change. Module template:
`docs/builds/fx_glitch.md`.

## Parity with StageLab JZB_Lofi_CRT
Source: `stagelab/ffgl/crt/CRT.cpp` + `CrtLogic.h`, preset file `stagelab/presets/JZB_Lofi_CRT.yaml`.
- All 19 controls exist under the same labels (Amount, Curvature, Scanlines, Mask, Halation, Degauss, Lines, Sharpness,
  Mask Size, Mask Strength, Corner, Vignette, Brightness, Border, Roll, Flicker, Hum Bar, Seed, Randomness). Ranges and
  defaults match too. The TD par names follow TD's naming rule: `Masksize`, `Maskstrength`, `Humbar`.
- **One difference:** the default Amount is **1**, not 0 like the plugin, so an added slot shows the tube at once.
- These are straight ports, with the same constants: the raster maths (each line a whole number of px, at least 3;
  square virtual px), the mask formula, the warp, the beam profile (`0.15 + 0.2 sqrt(L)`, gamma 2), the 24 Hz flicker
  step, roll lock-in at 0.6 screens/s or faster, the Degauss envelope (tau 0.45 s, over below 1 %), the purity waves,
  convergence directions and hum.
- Halation differs: 1/8 size, one compute pass of near + wide 7x7 Gaussians, instead of a 4-level pyramid. It gives
  the same kind of glow with a different falloff.
- The zkit preset names 1-5 are the plugin's recipe names.

## crt network (inside each instance)
`in1` -> `raster` (compute, rgba16float, vw x vh) <- `fb` (Feedback of `raster`) -> `glow` (compute, 1/8, linear) ->
`glow_src` (Switch: `glow_none` 1x1 while Halation 0) -> `fx` (compute, input size, `format useinput`) -> `out1`.
Control: `crt_logic` (Text DAT = the logic file), `clock` (Script CHOP with docked `clock_callbacks`, a `Frame` par =
absTime.frame) -> uniform array `uK[13]` on `raster` and `fx` (Arrays page, `array0chop clock`, vec4, uniformarray),
and `pulse_exec` (Parameter Execute: the Degauss pulse sets Degausstime/Degausscount, the Monitor menu applies the
whole monitor set).

Pages: **CRT** (Amount, Curvature, Scanlines, Mask off/aperture/slot/shadow/lcd, Halation, Degauss, Monitor),
**Raster** (Lines, Sharpness, Masksize, Maskstrength, Beammin, Beamgrow, Interlace off/alternate/weave, Interdim, Crawl,
Lineaxis x/y), **Screen** (Corner, Vignette, Brightness, Border, Curveaxis both/x/y, Overscan, Glass, Damper 0-3),
**Tube** (Phosphor colour/white/green/amber, Convx, Convy, Convedge, Focus, Persistr/g/b, Glowradius, Scanbar,
Scanbarwidth, Scanbarspeed), **Motion** (Roll, Flicker, Humbar), **Random** (Seed, Randomness), **State**
(Degausstime, Degausscount).

`monitor` = the Monitor menu (13 sets; zkit has 8 slots, so they live in a menu, and choosing one writes the whole
look): pvm, bvm, trinitron, broadcast, arcade, oldtv, c1084, greenterm, amber, portable, watchman, ledwall, deadset.
The values are tuned by eye from the hardware descriptions in FX2 AV-08, not measured from real sets.
zkit presets: 1 Broadcast Monitor, 2 Arcade, 3 Old Television, 4 Lost Sync, 5 Flat Scanlines, 6 Green terminal,
7 LED-wall safe, 8 Dead set. Presets store Monitor = custom, so recall is exact.

## crtfault network
`in1` -> `fx` (one compute pass) -> `out1`. Input 1 = `lum_src`: a Switch between `avg` (Analyze TOP, average
luminance, pulled only while Breathe != 0) and `lum_none` (1x1, 0.3). Plus `crt_logic`, `clock` and `pulse_exec`
(Degauss pulse; the Power toggle writes Powertime).

Pages: **Faults** (Amount, Roll, Tear, Jitter, Humbar, Degauss, Power), **Deflection** (Rollbar, Tearbands, Tearspeed,
Tearblank, Bend, Wobble, Wobblefreq, Breathe), **Hum** (Humspeed, Humcount, Humsoft, Arc, Degaussamt, Powerdur,
Border), **Random**, **State** (Degausstime, Degausscount, Powertime).

- Amount scales the continuous faults.
- Degauss and Power work at any Amount, so they can be hits and transitions. Power off (0.6 s by default): the picture
  squeezes to a bright line (0-35 %), the line shrinks to a dot (35-55 %), the dot fades (55-100 %), then black. Power
  on: the picture starts dim and small and grows.
- Exact passthrough needs all three: Amount 0, Power steady on, no Degauss running.
- Order: put `crtfault` **before** `crt`. The faults then move the raster that the tube draws, which is what
  deflection faults do on a real set.

## Build (live lane)
```python
# register the lane first: python3 tools/lane.py add FX_analog "crt lane"
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_analog.py').read(), ns)
ns['build']('/project1/lab')                                   # rack (+ ntsc1) if missing; idempotent
ns['add']('/project1/lab/FX_analog', 'crtfault')               # crtfault1
ns['add']('/project1/lab/FX_analog', 'crt')                    # crt1, after crtfault1
# put them first / disable ntsc1 in `slots` as wanted, then ns['rewire'](op('/project1/lab/FX_analog'))
```
Then run `td_errors` and `td_layout` (flow + check). Save a checkpoint after each verified step. Run risky first
builds on a build TD (b2/b3, T-120) or on scratch.

## LIVE CHECKS
Measure with the rack's test clip paused (`test_clip.par.play = 0`), or with a Constant TOP 1080x1920 rgba8 at
128/255 grey (call it G) wired into the rack's `in1` with Input = live. Read pixels only in an exec that comes **after**
the change (T-74): use `# allow-readback`, or frames >= 2. Parity checks save the data in TD and compare outside TD,
so TD never runs the slow numpy reference:
```python
L = op('/project1/lab/FX_analog/crt1/crt_logic').module          # td_exec:
exec(L.save_snippet('/project1/lab/FX_analog/crt1', '<repo>/output/crt_check/R4', 'crt'))
```
then in a shell: `python3 -I builders/fx_analog_crt_logic.py check output/crt_check/R4` -> {max, mean, within}.
Pass = `within >= 0.99` (share of values <= 2/255) **and** `max <= 8/255`. If it fails but `--flip` passes,
numpyArray rows come top-first: note that in LEARNINGS and use `--flip` from then on (R2).

| # | Check | How | Expected |
|---|---|---|---|
| R1 | Compiles + array uniform | build; `td_errors` on crt1 + crtfault1; check `fx` / `raster` info has no GLSL errors; `op('clock').numSamples` | no errors; `clock` = 13 samples x chans x y z w; raster 270x480, glow 135x240 at 1080x1920 (Lines 480) |
| R2 | Row order | R4 with Roll stopped mid-picture (Roll 0.4 for 0.5 s, then Seed etc. unchanged; read while rolling) | `check` passes without `--flip` (expected: numpyArray row 0 = bottom). If not, record in LEARNINGS |
| R3 | Exact passthrough | crt1 Amount 0 (no Degauss): max abs diff of `in1` vs `out1` (numpy, 4 frames later); the same for crtfault1 (Amount 0, Power on); slot enabled 0; Panic | 0, 0, 0, 0 |
| R4 | crt parity | input G, pars Curvature 0, Corner 0, Vignette 0, Mask off, Halation 0, Scanlines 1, Lines 480, Brightness 1 -> save + `check` | passes; output columns repeat every 4 rows; on x=540 rows 0-3 read **78, 120, 120, 78** (/255), whole-frame mean R **99.2/255** |
| R5 | crt parity, defaults | the clip (paused), default pars with Halation 0 -> save + `check`; again with Mask slot, Convx 1.5, Focus 0.5, Damper 2, Lineaxis y | passes all three |
| R6 | Masks | input white, Scanlines 0, Halation 0, Curvature/Corner/Vignette 0, Brightness 1, Masksize 6, Maskstrength 0.5 | lit px = 255, unlit = **180** (sqrt 0.5); frame mean R = G = B: aperture **0.805**, slot **0.789**, lcd **0.789**, shadow **0.772**; on the LED preview no moire at 6 px or more |
| R7 | Curvature + border | input G, Curvature 1, Corner 0.3, Halation 0 | pixel (0,0) = (0,0,0,1); bottom row black up to x **505** (+-2); Border transparent -> (0,0,0,0) |
| R8 | Roll | Roll 0.4 for 0.5 s; read a frame: count rows of x=540 that are pure black; then Roll 0 and wait 2 s | **153 +- 2** black rows (8 % bar); after Roll 0 the picture locks in <= 1.7 s and a later read equals the Roll-never-touched output (diff 0) |
| R9 | Degauss | Amount 0, pulse Degauss: Degausscount +1, Degausstime = absTime; diff vs input at 0.2 s and at 2.5 s | 0.2 s: mean diff > 0.02 (swirl + wobble); 2.5 s: **0** (exact again) |
| R10 | Monitor + presets | choose Monitor `pvm`; compare pars with `crt_logic.monitor_values('pvm')`; zkit Recall 1-8 | equal, every key; Recall sets Monitor = custom and the stored values |
| R11 | Persistence | Persistg 0.5 (R/B 0), input white for 1 s then black (switch input): read `raster` green on the next 3 frames | 0.5, 0.25, 0.125 (+-1/255 of rgba16f); R and B go to 0 at once |
| R12 | Interlace | clip playing, Interlace weave: rows 2k and 2k+1 of `raster` come from different frames (diff of neighbouring raster rows > diff with Interlace off); alternate: every other line dimmed by Interdim, swapping each frame | weave shows combing on motion; alternate: line mean ratio **(1-Interdim)** on even vs odd frames |
| R13 | Halation | input black with a white 200x200 square, Halation 1 | glow > 0 within ~100 px of the square (row of x = square edge + 40 px > 10/255); Halation 0 -> `glow` does not cook (`glow.cookFrame` stays the same) |
| R14 | Cost + fps (crt) | defaults (Halation 0.25, aperture): 120 frames, out1 pulled, cpu+gpu per pass (T-81 (4)); project fps over 300 frames with the other lab COMPs parked | raster < 0.3 ms, glow < 0.2 ms, fx < 1.5 ms (2.2 ms with Convx != 0: 3 beams), clock CPU < 0.15 ms; **sum <= 3 ms**; 60 fps. If fx > 2 ms, note it in LEARNINGS (the mask + 2 raster taps per px should be ~1 ms) |
| F1 | crtfault compile + passthrough | build; R3 for crtfault | no errors; diff 0 |
| F2 | crtfault parity | input G or the clip (paused); Tear 0.5, Tearspeed 0, Jitter 0.5, Bend 0.3, Wobble 0.5, Humbar 0.5, Randomness 0 -> save + `check` (module crtfault) | passes |
| F3 | Power off / on | input G, Power off; read at about 0.15 s, 0.27 s, 0.5 s, 0.8 s after (frames at 60 fps: 9, 16, 30, 48) | 0.15 s: **944 +- 4** lit rows on x=540; 0.27 s: **8** lit rows, **542 +- 4** lit px on row 960; 0.5 s: only the centre dot; 0.8 s: all black (alpha 1). Power on: dim, small, full after Powerdur. LIVE CHECK: watch for a dropped frame, since Powertime is in absTime |
| F4 | Hum | input G, Humbar 1, Humspeed 0 | darkest row value **76.8/255** (40 % dip), lightest 128; bars = Humcount |
| F5 | Breathe | the clip playing, Breathe 1: `avg` cooks only while Breathe != 0; `avg` is 1x1 with the luminance in **r** (LIVE CHECK: the Analyze TOP's output layout) | the picture size follows the brightness (+-2.4 % at lum 0 / 1) |
| F6 | Roll / Degauss / arcs | Roll 0.4 then 0 (locks like R8); Degauss at Amount 0 (like R9); Arc 1: flashes about 2.4 times a second at 60 fps | as stated |
| F7 | Cost + fps | defaults + Tear 0.5 + Jitter 0.5 | fx < 0.5 ms, clock < 0.15 ms; 60 fps |
| C1 | Chain | crtfault1 -> crt1 -> Panic: Panic on = diff 0 vs img_src; both on, cost sum <= 3.5 ms; project 60 fps | as stated |

Facts that need TD and that the checks above settle:
- A compute-mode GLSL TOP takes a CHOP uniform array (particles uses one on 31550).
- The Script CHOP `Frame` pattern cooks the clock exactly once per frame (PX T-113). Count
  `clock.cookFrame` increments over 60 frames: expect 60.
- Feedback TOP history at raster size: `fb` follows the raster size, and `raster` ignores it while the sizes differ
  (T-35 guard).
- Parameter Execute `onValueChange` fires for the Monitor menu and the Power toggle, and `onPulse` for Degauss. Toggle
  `active` after a text rewrite (T-97).
- A menu par takes `q.val = 'aperture'` by name in pulse_exec.

## Verified live (26 Oct, 31550; scratch TD with other lanes, then brought home to main)
- **Fixes found live:** (a) `CL = {}` lost TD's names (`textDAT` NameError in `td_common`) -> `dict(globals())` in
  both modules; (b) the `clock` Script CHOP stored its state in its own storage -> cook dependency loop warning every
  cook -> state in `crt_logic.CLOCK_STATE[path]`; (c) raster uniform `uR.yz = me.width/height` -> loop warning on size
  change -> `me.par.resolutionw/h.eval()`; (d) `SAVE_SNIPPET` read rows from storage -> now from the `clock` CHOP
  (exactly what the shader got); (e) stages 3 Raster + 4 Halation merged (fb read by reference landed in the
  Halation box).
- R1 / F1: `td_errors` clean; raster 270x480, glow 135x240; clock 13 samples x (x y z w); no loop warnings after (b)/(c).
- R3 / F1 passthrough: crt Amount 0 + crtfault Amount 0 -> 0; each slot off -> 0; Panic -> 0.
- R4 (grey 128, Mask off, Scanlines 1): column x=540 rows 0-3 = 78, 120, 120, 78; mean R 99.0/255 (doc 99.2); `check`
  max 0.0016, within 1.0. R2: R5 on the (asymmetric) clip passes without `--flip` (row 0 = bottom).
- R5 (clip paused, Halation 0): defaults max 0.0032; Mask slot + Convx 1.5 + Focus 0.5 + Damper 2 max 0.0054;
  Lineaxis y max 0.0040; within 1.0 each.
- R9 Degauss at Amount 0: count +1, 0.47 s mean diff 0.047; 4.3 s diff 0. crtfault: 0.85 s 0.019; 4.95 s 0.
- R10: Monitor `pvm` = `monitor_values('pvm')` exactly; zkit Recall 1-8 exact (twice).
- F2 (Tear 0.5, Tearspeed 0, Jitter 0.5, Bend 0.3, Wobble 0.5, Humbar 0.5, Randomness 0): max 0.0027, within 1.0.
- F3: Power off -> 2.5 s later rgb 0, alpha 1; Power on -> 0.68 s later diff 0 vs input.
- Cost (clip playing, 120 frames): crt defaults 1.62 ms median (fx 0.63, glow 0.27, raster 0.16); crtfault Tear +
  Jitter 0.78 ms (fx 0.53); chain vhs + crtfault + crt 2.74 ms. `clock` Script CHOP CPU 0.2-0.7 ms each (doc
  estimate < 0.15; Rosetta Python on a loaded scratch TD).
- Not run: R6-R8, R11-R13, F4, F5, F7 fps.
- Main TD: FX_analog with ntsc1 (off), vhs1 (on), signalloss1 (off), crtfault1 (off), crt1 (on, Old Television),
  errors clean, restaged, parked, saved (JazibTD_home.296). Captures: `output/project1_lab_FX_analog_out1_2026-10-26T15-19-56-207Z.png`
  (vhs worn tape -> crt), scratch window `output/window_TouchDesigner_2025.31550_Users_vyro_Docu_2026-10-26T15-19-57-455Z.png`.

## Not done / open
- Halation is not the plugin's pyramid. Glass is a simple highlight, with no reflection input. There is no bezel image.
- Persistence runs at raster resolution, before roll: a rolling picture keeps its trails attached to the picture,
  not to the glass.
- The arc flash and the purity swirl are not in the numpy references. They are checked by eye and by diff only
  (R9 / F6).
- The clock's real time stops while a slot is bypassed. On re-enable, motion resumes with dt at most 0.25 s, the
  history restarts after a gap, and Degauss and Power keep running in absTime (as in JZB).
