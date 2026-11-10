# fx_analog_vhs: FX_analog module `vhs` (offline prep, 26 Oct 2026, target TD 2025.31550)

VHS tape look for `/project1/lab/FX_analog` (rack = `builders/fx_analog.py`, the FX_glitch rack; module template:
`docs/builds/fx_glitch.md`). Research: `docs/research/FX2_analog_video_hardware_emulation.md` AV-17, FX0 row 13. It is
the TD twin of StageLab's **JZB_Lofi_VHS** (`stagelab/ffgl/vhs/VHS.cpp` v2, guide `stagelab/guides/JZB_Lofi_VHS.md`;
read-only): same control names, labels, ranges, defaults (except Amount: 1 here, the TD module default) and the four
StageLab recipes as presets 1-4, so a look moves between Arena and TD. **Nothing here has run in TD yet: every
behaviour below is a LIVE CHECK.** Offline status: `python3 -I -m unittest discover -s test -p 'test_fx_analog_vhs.py'`
(34 tests incl. `signalloss`: specs, StageLab parity, logic, numpy reference, dry build on a fake TD, glslc compile of every pass).

Files: `builders/fx_analog_vhs.py` (pars, presets, 3 shaders, `build`), `builders/fx_analog_signal_logic.py` (maths
shared with `signalloss`, numpy reference `ref_vhs_*`, GLSL lib, `stamp`, Pulse exec), `test/test_fx_analog_vhs.py`.

## Build (td_exec, ~2 min)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_analog.py').read(), ns)
ns['build']('/project1/lab')                        # rack (+ ntsc1) if FX_analog does not exist yet; idempotent
ns['add']('/project1/lab/FX_analog', 'vhs')          # -> vhs1, wired last, zkit panel + 7 presets
```
Lane rules first (CLAUDE.md): `python3 tools/lane.py add FX_analog "<label>"`, `FX_analog.allowCooking = True`, other
idle COMPs parked, `td_checkpoint` after each verified step, `td_layout` flow, `td_errors` clean.

## Network (inside `vhs1`)
`in1` -> `enc` (compute, rgba16float, virtual raster) -> `sig` (compute, rgba16float) -> [`sprev` Cache TOP -> `prev_src`
Switch, Interlace only] -> `fx` (compute, input size, `useinput`; inputs in1, sig, prev_src, `stamp`) -> `out_sel`
(Switch: 0 = in1, 1 = fx) -> `out1`. `pulses` (Parameter Execute): Glitch -> `Glitchtime` = absTime.seconds,
`Glitchcount` + 1. `stamp` = 1x1 cook clock (T-111): a gap > 0.25 s means the previous signal frame is stale, so
Interlace shows the current one. `out_sel` = 1 while Amount > 0 or a Glitch burst is running (< 1.842 s after the
press), else in1 straight out: enc / sig / fx are not pulled at Amount 0 (cost 0).

Virtual raster (`fx_analog_signal_logic.raster`, StageLab `VhsRasterFor`): line pitch = max(3, lround(L / Lines)) px,
vh = ceil(L / pitch) lines, vw = lround(vh * 0.75 * S / L) samples; S, L = width, height (Line axis X) or height, width
(Line axis Y: the canvas is a TV on its side, lines run vertically, the smear goes down).

## Pars
| Page | Par (label) | What |
|---|---|---|
| VHS | Amount | 0 = exact passthrough (unless a Glitch burst runs). Also scales wobble, noise, band, scanlines |
| VHS | Bleed | chroma smear to the right: tau = (0.3 + 4.7 Bleed) samples x tape speed |
| VHS | Wobble | slow line bending (2.5 samples) + per-line jitter (<= 1 sample), x tape speed jitter |
| VHS | Tracking | rolling tracking band (StageLab: 9 s sweep at Randomness 0) + snow streaks |
| VHS | Glitch (pulse) | tracking-error band, 1 -> 0 over 1.84 s (tau 0.4 s), works at any Amount |
| Signal | Lines 240/480/576, Sharpen, Chroma Shift (0-8 samples), Noise, Dropouts | as StageLab |
| Signal | Tapespeed SP/LP/EP | +0/1/2 luma low-pass passes, chroma tau x1/1.35/1.7, noise x1/1.4/2, jitter x1/1.3/1.7 |
| Signal | Generations 1-5 | dubs: luma passes + (G-1), chroma = G cascaded filters (negative binomial), shift x (1 + 0.5 (G-1)), saturation x 0.92^(G-1) |
| Signal | Flagging | top ~14 % of lines bend sideways (time-base error after vertical sync) |
| Signal | Dropcomp | dropout dashes filled from the line above instead of white |
| Look | Scanlines, Saturation, Warmth, Head Switch, Interlace | as StageLab |
| Look | Headlines | head-switch zone height in virtual lines (StageLab fixed 6) |
| Look | Lineaxis | Along X (TV upright) / Along Y (TV on its side) |
| Random | Seed 0-99, Randomness | as StageLab: Randomness 0 = loops per Seed (band 9 s, dropouts every 48 noise steps) |
| State | Glitchtime, Glitchcount | written by the Glitch pulse; uniforms read them |

Noise, jitter and dropouts step at <= 24 Hz (every 3rd frame at 60 fps; `NOISE_STEP_EXPR` uses project.cookRate).
Presets (zkit): 1 home video, 2 worn tape, 3 clean retro, 4 breakdown (StageLab recipes), 5 fresh rental, 6 lp bootleg
(EP, 3 generations, dropout compensation), 7 clean tape (deterministic: Wobble / Tracking / Noise / Dropouts /
Flagging 0, Head Switch + Interlace off = `ref_vhs_clean`, used by V3).

## LIVE CHECKS (each with the expected number; ~15 min in total)
Setup: rack `Input` = test, `op('/project1/lab/FX_analog/test_clip').par.play = 0` (paused picture), other slots
disabled in `slots` (enabled 0) so `vhs1`'s in1 = the test clip. Read pixels in a separate exec >= 3 frames after any
change (T-74, T-111 (4)); `I = op('.../vhs1/in1').numpyArray(delayed=False)`, `O = op('.../vhs1/out1').numpyArray(...)`.

| # | Check | Expected |
|---|---|---|
| V1 | Build: `td_errors` on vhs1 (all 3 compute DATs compile, `rgba16float` accepted as a GLSL TOP format) | no errors; `enc` 203x480 at Lines 480 |
| V2 | Raster: `enc` width x height for Lines 240 / 480 / 576 | 101x240, 203x480, 270x640; Lineaxis y: 288x216, 480x360, 480x360 |
| V3 | Parity: preset 7 (clean tape), Seed 1. In TD: `lg = {}; exec(open('<repo>/builders/fx_analog_signal_logic.py').read(), lg); R = lg['ref_vhs_clean'](I)`; `d = abs(O[..., :3] - R[..., :3]) * 255` | 99.9 % of px d <= 2, mean d < 0.5, max d <= 8 (float16 + GPU division rounding at sample edges). Repeat with Lines 240 + Generations 3 + Tapespeed EP (`ref_vhs_clean(I, lines='240', gens=3, tape='ep')`) and with Lineaxis y (`axis=1`): same bounds |
| V4 | Amount 0 (Glitch idle): `out_sel.par.index` and max abs O - I | 0 and 0.0; slot enabled 0 / mix 0 / rack Panic: 0.0 |
| V5 | Bleed one-sided: V3 already covers it; eyeball a capture of preset 2 | colour trails to the right only (Lineaxis y: downward) |
| V6 | Head switch: preset 7 + Head Switch on (6 lines), Lines 480 | rows y >= 24 identical to the Head Switch off read (max diff 0), > 50 % of px in rows 0-23 changed |
| V7 | Glitch at Amount 0: pulse `op('.../vhs1').par.Glitch.pulse()`, read at ~0.3 s | `Glitchcount` +1, out_sel 1, changed rows inside (gpos +- 0.18) x 1920 with gpos = `glitch_pos(Glitchcount, Seed, Randomness)` (+ <= 0.08 drift); after 2.0 s out_sel 0 and diff 0 |
| V8 | Interlace on, preset 7, clip PAUSED | output equal to Interlace off (max diff 0: previous frame = current) |
| V9 | Interlace on, clip PLAYING, read I and O in the same exec | even virtual lines (rows with (y // 4) even at Lines 480) within V3 bounds of `ref_vhs_clean(I)`; odd lines differ where the picture moves |
| V10 | Noise rate: preset 1, read `fx` uniform `uD.y` (noise step) twice 1 s apart at 60 fps | +20 steps (24 Hz cap: 3 frames per step) |
| V11 | Presets: zkit Recall 1-7 | pars exactly as `PRESETS` (menus by index) |
| V12 | Cost: pane on another COMP, out1 pulled per frame, 120 frames, preset 4 (breakdown, worst case) | enc + sig + fx GPU <= 1.5 ms median (estimate 0.1 + 0.05 + 0.6-1.0); project 60 fps (cookRate untouched) |

Facts this module assumes from other live work (still worth a glance): compute `uTDOutputInfo.res.zw` (motion_trail),
Cache TOP `outputindex -1` = previous cook (mosh `cprev`), Parameter Execute `onPulse` with `pars` = the pulse names
(mosh used `*`), `math.ceil` / `project.cookRate` inside a uniform expression, menu `eval()` = the name string (Lines).
Anything that fails: fix the builder, add a LEARNINGS entry (T-nn), rerun the offline tests.

## Verified live (26 Oct, 31550; scratch TD with other lanes, then brought home to main)
- **Bug found at build:** `fx` has 4 inputs (in1, sig, prev_src, stamp) and a GLSL TOP has 3 connectors from Python
  (T-84): `IndexError` in the rack's compute helper. `builders/fx_analog.py` now makes a **GLSL Multi TOP** (compute
  mode, any input count; probed: maxInputs 9999, modes vertexpixel / compute) for passes with > 3 inputs.
- V1: `td_errors` clean, `enc` 203x480. V2: 101x240, 203x480, 270x640; Lineaxis y 288x216, 480x360, 480x360 (exact).
- V3 parity (preset 7, Seed 1, clip paused): 100 % of px d <= 2, mean 0.258, max 0.87 (of 255); Lines 240 +
  Generations 3 + EP: 100 %, mean 0.257, max 0.74; Lineaxis y: 100 %, mean 0.258, max 0.81.
- V4: Amount 0 -> out_sel 0, max diff 0. V6: Head Switch on changes only numpy rows 0-23 (the bottom 24 px; 99.9 % of
  their px), rows above max diff 0. V8: Interlace on with the clip paused = Interlace off (diff 0).
- V7: Glitch at Amount 0 -> Glitchcount +1, out_sel 1, changed rows 678-947 inside the expected band 316-1007
  (gpos 0.345); 5 s later out_sel 0, diff 0.
- V11: zkit Recall 1-7 exact (the first Recall right after the panel build did not apply, as with ntsc; later runs exact).
- V12 cost (breakdown preset, clip playing, 120 frames): enc 0.25 + sig 0.11 + fx 0.78 = 1.15 ms; COMP total 2.07 ms
  median (stamp 0.21, sprev 0.08). V10 (noise step rate) not run.
- Main TD: loaded from `output/transfer/FX_analog.tox` (ntsc1 slot off, vhs1 on), errors clean, restaged, parked, saved
  (JazibTD_home.284). Capture (worn tape): `output/project1_lab_FX_analog_out1_2026-10-26T15-09-05-099Z.png`.

## Perf lane 2 (27 Oct, b2, 31550)
- `fx`: everything per tape row (wobble, jitter, flagging, tracking / Glitch band, head switch, dropout pick) is
  computed once per 8x8 group by lanes 0-7 into shared memory (`sR`, `sD`), and the 4x4 noise lattice hashes by lanes
  32-47 (`sN`, pixels outside the block fall back to hashing); same maths. Paired same-frame A/B (T-145): fx GPU 0.61x.
  Old vs new text on the same frame: max 1/255 on 0.004 % of px. Offline: 34 tests (glslc) pass.
- After `upgrade` on b2: V3 (preset 7, Seed 1, clip paused) 100 % d <= 2, mean 0.258, max 0.75; V4 Amount 0 ->
  out_sel 0, max diff 0. (The first b2 attempt hung during a par set, at the same second as b4's blackhole stall, T-193.)
- Home: main ntsc1 / plasma1 / vhs1 `upgrade` one per exec (un-parked, 0 errors, new texts in), parked, saved
  JazibTD_home.703; library FX_analog 0.2.0.

## Not done / open
- Crease (S-shaped travelling band, AV-17 item 8), luma pre-emphasis overshoot beyond the Sharpen ring, chroma phase
  wobble (rainbow edges), SP/LP/EP head-switch band height: later if wanted.
- Alpha: the module keeps the input alpha per pixel (StageLab smears alpha into transparent areas; FX_analog works on
  opaque pictures).
- Transport (pause bar / shuttle, AV-18) is a separate module (FX0 row 54).
