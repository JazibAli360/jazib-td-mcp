# fx_glitch module `timedisplace` (slit-scan / time map, DG-13 / D10) - offline prep, 26 Oct 2026

Status: **live on the main TD (26 Oct, 31550), slot `timedisplace1` in `/project1/lab/FX_glitch` (enabled 0).** Map encoding corrected live (T-122). Builder, map shader, pure maths, numpy reference and tests are done;
everything marked **LIVE CHECK** needs TD 2025.31550. Rack + module template: `docs/builds/fx_glitch.md`. Technique:
`docs/research/FX6_probes_31550.md` probe 4b (native ring, ~0.35 ms) and FX1 DG-13.

Files: `builders/fx_glitch_timedisplace.py` (module), `builders/fx_time_ring.py` (ring chain shared with
`timeshuffle`: 2 real users), `builders/fx_time_logic.py` (`td_offsets` = the map shader in numpy, `ref_timemachine`,
`decode_frame_code`, `vram_mb`), `test/test_fx_glitch_timedisplace.py` (24 tests; glslc compile against TD stubs).
Needs the rack's `_pars` 'TOP' style (`Maptop`), which is in the working tree of `builders/fx_glitch.py` (mosh lane):
commit that first, or the add fails on `Maptop`.

## Network (inside the instance COMP)
| Stage | Ops |
|---|---|
| 1 In | `in1`, `map_sel` (Select TOP: `Maptop`, else `in1`) |
| 2 Time map | `ring` (Texture 3D TOP, `cachesize` = Depth, input format, full or half res) ; `stamp` (1x1 rgba32float compute, readwrite: x now, y previous cook, z cooks since the ring restarted, w ring key) ; `map` (compute, rgba32float, readwrite, Mapres x input size) ; `tmachine` (Time Machine TOP: ring on input 0, map on input 1, `blackoffset` -(Depth-1) indices, `whiteoffset` 0, `depthoffset`, output = in1 size) |
| 3 Out | `out_sw` (Switch: Amount 0 = in1, exact) -> `out1` |

The map writes grey `m = 1 - offset/(Depth-1)`. `offset = Delay + shape * Amount * (Depth-1)`, clamped to
`[0, min(Depth-1, stamp.z)]`: after a restart (slot bypassed > 0.25 s, Amount 0, Depth or Quality changed) the time
range grows back one cook per cook, so there are no stale or empty slices. Depth is counted in cooks, not seconds
(FX6 4b), so it stretches when frames drop.

| Par | What |
|---|---|
| Amount | share of the ring span (0 = exact passthrough via `out_sw`) |
| Depth | ring slices; VRAM at 1080x1920 8-bit: 32 = 265 MB, 60 = 498 MB, 120 = 995 MB (half res: 1/4) |
| Quality | full / half res ring |
| Delay | frames added to every pixel |
| Mode | ramp (angle; 0 = bottom now, top oldest), radial, spiral (Twist), luma, noise (Scale, Speed), external (`Maptop`: any TOP, e.g. flow, mask, audio texture) |
| Centerx / Centery | ramp pivot, radial / spiral centre |
| Smooth | the map integrates over time (map melt) |
| Mapres | map at full, half (default) or quarter res (the Time Machine filters it) |
| Repeat, Mirror, Phase | several slits; triangle instead of saw; scroll (cycles/s) |
| Curve, Steps, Invert | gamma; hard time bands; flip |
| Jitter, Jittersize, Jitterrate | random per-row time offset (rows in picture px), redrawn Rate times a second |
| Seed | noise / jitter hash |

Presets (zkit): 1 slitscan, 2 time tunnel, 3 spiral warp, 4 liquid time (Depth 48), 5 scan bands.

## Build (td_exec, main TD after the scratch run)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_glitch.py').read(), ns)
ns['add']('/project1/lab/FX_glitch', 'timedisplace')     # -> timedisplace1, wired last
```
Order: `python3 tools/lane.py add FX_glitch "<label>"`, `allowCooking = True`, scratch TD first (`td_exec
target:'scratch'`, T-83: new op types texture3dTOP / timemachineTOP / selectTOP in a compute rack), then main.
Remove with `ns['remove'](..., 'timedisplace1')` (safe_destroy). Park + `lane.py remove` at the end.

## Frame-code probe (used by checks 3-7; also by timeshuffle)
Every input frame carries its own number, so the output says which frame each pixel came from:
```python
lab = op('/project1/lab'); c = lab.op('fxt_probe') or lab.create(constantTOP, 'fxt_probe')
c.par.outputresolution = 'custom'; c.par.resolutionw, c.par.resolutionh = 1080, 1920; c.par.format = 'rgba8fixed'
c.par.colorr.expr = '(absTime.frame % 256) / 255.0'; c.par.colorg = c.par.colorb = 0; c.par.alpha = 1
op('/project1/lab/FX_glitch').inputConnectors[0].connect(c); op('/project1/lab/FX_glitch').par.Input = 'live'
```
Read (separate exec, >= 3 frames after any change, `# allow-readback`, T-74/T-111 (4)):
```python
# allow-readback
import numpy as np; m = op('/project1/lab/FX_glitch/timedisplace1')
a = m.op('in1').numpyArray(delayed=False)[..., 0]; b = m.op('out1').numpyArray(delayed=False)[..., 0]
z = m.op('stamp').numpyArray(delayed=False)[0, 0]
off = np.mod(np.round((a - b) * 255), 256)        # = fx_time_logic.decode_frame_code
```
Afterwards: Input back to auto, disconnect, `safe_destroy(op('/project1/lab/fxt_probe'))`.

## LIVE CHECKS (expected numbers from `fx_time_logic`; ~15 min)
1. **Builds clean:** `td_errors` on the instance = none; `map` and `stamp` compile (GLSL info DAT empty / no
   checkerboard); `td_layout` ok. Record any 31550 API difference (Select TOP `top` as an OP expression, Texture 3D
   `type`/`cachesize` names) in LEARNINGS.
2. **Exact passthrough** (clip paused, img_src vs out1, numpy max abs diff): Amount 0 -> 0; slot enabled 0 -> 0;
   mix 0 -> 0; Panic -> 0. Control (Amount 1, slitscan, clip playing) -> mean diff > 0.
3. **Ramp offsets** (probe, Mapres full, Depth 32, Amount 1, preset 1, wait > 1 s): per row y (counted from the
   bottom of the picture) `off(y) = 31 * (y + 0.5) / 1920`: rows 0 / 480 / 960 / 1440 / 1919 = **0.008 / 7.758 /
   15.508 / 23.258 / 30.992**; decoded values within +-1 of these (8-bit rounding of the interpolated code), mean
   abs error <= 0.5 over all rows, every column of a row equal. If the numbers rise toward the top of the numpy array
   instead, numpyArray row 0 is the top: note it (T-entry) and flip. Frame drops show as +1 steps; take the row
   median.
4. **Fill after restart:** Amount 0 for 1 s, then 1; read at once and 0.25 s later: `max(off) == min(z, 31)` (+-1),
   z small at first (stamp counts cooks since the restart). No black or old frames anywhere (`off <= z`).
5. **Steps 4:** decoded offsets take only 4 values, **0 / 10 / 21 / 31** (+-1) (reference 0, 10.333, 20.667, 31).
6. **Radial:** centre pixel (540, 960) ~ **0.02**, (540, 0) and (540, 1919) **~27.0**, corner (0, 0) **~31.0** (+-1).
7. **Depth 32 -> 60:** stamp w changes from 128 to 240, z restarts at 0, offsets grow back to 59 (+-1) within ~1 s;
   no errors. Quality half: `out1` still 1080x1920, check 3 within +-1.5 (half-res ring is filtered up).
8. **External map:** Mode external, `Maptop` = a Ramp TOP (vertical, black bottom): same as check 3 within +-1.
   Empty Maptop -> map uses the picture's luma (no error).
9. **Which map channel the Time Machine reads** (we write grey RGB, alpha 1, so both work): record the fact.
   **Texture 3D interpolation:** Steps 0 gives fractional offsets; out codes between two frames confirm the
   interpolation FX6 saw (241 distinct row values at 32 slices).
10. **Cost** (out1 pulled, pane elsewhere, other lanes parked, 120 frames): ring + tmachine + map + stamp target
    **<= 0.6 ms** (FX6: tex3d 0.12-0.15 + time machine 0.21; map ~0.05-0.15 at half res); project 60 fps,
    `cookRate` untouched. Also Depth 120 full: cost and VRAM (~1 GB by the table; Activity Monitor GPU memory).
11. **Presets** 1-5 recall exactly (zkit); each looks as named on the stored clip; capture out1 + network.
12. `td_checkpoint`, save, park, `lane.py remove`; results go into this file ("Verified live") + a T-entry.

## Not done / open
- Flow-magnitude map (DG-01 motion slows time) and audio spectrum map: use `Maptop` with the mosh estimator / an
  audio TOP until a module needs them built in.
- Feedback melt is the map's `Smooth` (the map integrates); a full displace-feedback melt is `feedbackkill`.

## Verified live (26 Oct, 31550; scratch first, then main; T-122)
- Builds clean on scratch and main (`td_errors` none; the tmachine "W-Offset" warning only before the ring's first cook).
- **Map encoding fixed:** the Time Machine reads `(1 - m) * Depth - 1` slices, so the map now writes
  `m = 1 - (offset + 1) / Depth` (shader, Smooth inverse, `fx_time_logic.encode`). Probe = a 16f in-place cook counter
  (not the absTime frame code, which skips frames): ramp Steps 32 -> all 32 bands exactly k cooks back; Depth 60 / Steps
  60 -> 60/60 exact, stamp w 128 -> 240, z restarted. Before the fix half the bands read k-1 or a 2-frame blend.
- Ramp (Steps 0, before the fix, 8-bit counter): offsets 0/7/15/23/31 at rows 0/480/960/1440/1919, every column of a
  row equal; radial (scratch): centre 0, (540,0)/(540,1919) 27, corner 31 (= reference).
- Exact passthrough (clip paused, img_src vs out1): Amount 0, slot enabled 0, mix 0, Panic -> max diff 0. Control
  (slitscan, clip playing): max 0.41, mean 0.0045.
- Cost (slitscan, Mapres half, 8-bit ring, 120 pulled cooks): 1.09 ms median (tmachine 0.47, map 0.15, stamp 0.13,
  ring 0.11), p90 2.9. All three time modules on with the test clip: td_watch 59.9 fps (min 56.6), cookRate 60.
- Capture: `output/project1_lab_FX_glitch_out1_2026-10-26T15-09-21-392Z.png` (timedisplace + timeshuffle +
  feedbackkill stacked). Checkpoint `output/checkpoints/FX_glitch/FX_glitch_20261026-200954.tox`.
- Not run live: presets 2-5 by eye, Quality half, external Maptop, Depth 120 VRAM.
