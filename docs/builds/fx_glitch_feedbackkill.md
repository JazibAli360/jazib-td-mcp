# fx_glitch module `feedbackkill` (feedback destruction / generation loss / burn-in, DG-21) - offline prep, 26 Oct 2026

Status: **live on the main TD (26 Oct, 31550), slot `feedbackkill1` (enabled 0).** Everything marked **LIVE CHECK** needs TD 2025.31550. Rack + template:
`docs/builds/fx_glitch.md`; spec FX1 DG-21.

Files: `builders/fx_glitch_feedbackkill.py`, `builders/fx_time_logic.py` (`fk_colour` = the point-wise generation,
`fk_shift` / `fk_edge` = the exact integer-shift path, `hue_rotate`, `fk_mean_grid`, `fk_ticks`),
`test/test_fx_glitch_feedbackkill.py` (19 tests: glslc compile of the 3 shaders, point-wise maths, a 300-generation
simulation of every preset that must not lock to black/white).

## Network
`in1` -> `fb` (Feedback TOP, `top` = fx) -> `stamp` (1x1 rgba32float, ONE 16x16 workgroup: x now, y previous cook,
z cooks since fresh, w mean luma of the previous state on a 64x64 grid) -> `fx` (one compute pass = one generation,
format 16f or input) -> `outc` (compute, input format: `mix(in1, state, Amount)`, Amount 0 = in1 exactly) -> `out1`.
Three compute passes (T-46/T-47); no pixel-mode GLSL.

One generation (`fx`): resample the previous state (zoom / rotate about the centre, shift px per generation,
displace by its own luma gradient, Curl = along contours; integer shifts with no zoom/rotate/displace use texelFetch:
exact, no blur creep) -> filters at Radius (Soften, Sharpen, Burn = dilate brights) -> colour (hue step about the grey
axis, saturation, contrast + bright, wavefold) -> x Decay -> feed the live picture (mix / lighten / darken /
difference / add, Leak x Key) -> Autogain (pull the mean toward Target; it also lifts pure black) -> Crush bits
(+ dither) -> Noise -> clamp 0..1. Rate = generations per second (0 = every cook), Hold freezes, Reset (toggle) =
live; a gap > 0.25 s (slot bypassed / panicked) restarts from live.

Pages: **Feedback** (Amount, Leak, Feed, Key, Decay, Rate, Hold, Reset, Precision 16f / 8bit), **Transform** (Zoom,
Rotate, Shiftx, Shifty, Centerx, Centery, Edge mirror/repeat/clamp/black, Displace, Curl, Radius), **Damage** (Soften,
Sharpen, Burn, Huestep, Saturation, Contrast, Bright, Fold, Crush, Dither, Noise, Autogain, Target, Seed).
Presets: 1 photocopy decay, 2 tape dub, 3 burn-in, 4 acid loop, 5 melt flow. Chain `dct` (Generation) before or
after this module for JPEG-of-a-JPEG patina; it is not duplicated here.

## Build
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_glitch.py').read(), ns)
ns['add']('/project1/lab/FX_glitch', 'feedbackkill')      # -> feedbackkill1
```
Scratch TD first (T-83: a compute pass with `shared` + `barrier()` reduction and a format expression), then main.

## LIVE CHECKS (~15 min; stored clip; reads in separate execs >= 3 frames after a change, `# allow-readback`)
1. **Builds clean:** `td_errors` none; fx / stamp / outc compile. `fx` format follows Precision (16f -> 16-bit float;
   8bit -> the input's); Feedback TOP passes the 16f state on (record if it does not).
2. **Exact passthrough** (clip paused): Amount 0 / enabled 0 / mix 0 / Panic -> max diff **0**.
3. **Identity holds** (all defaults, Leak 0, clip playing): two reads of `fx` 0.5 s apart are identical (max diff
   **0**: the texelFetch path does not creep), while in1 changes.
4. **Exact shift:** Leak 0, Edge repeat, Shiftx 1 (Precision 8bit or 16f): read `fx` + `stamp` (A, zA), later
   (B, zB): `B == np.roll(A, zB - zA, axis=1)` exactly (`fk_shift`), with zB - zA = cooks between the reads.
5. **Hue step 120, Leak 0, 16f:** `B ~ hue_rotate(A, 120 * (zB - zA))` within 2/255; three generations = the
   start picture again.
6. **Crush 2** (Leak 0.1): out1 holds only the values **0, 85, 170, 255** (8-bit) per channel.
7. **Autogain:** live = Constant TOP 0.05 grey into FX_glitch in1 (as the frame-code probe in
   `fx_glitch_timedisplace.md`, constant colour), Leak 0, Autogain 1, Target 0.45: after 2 s the mean luma of `fx` is
   **0.45 +- 0.02** and `stamp` w matches the numpy mean of `fx` within 0.01 (64x64 grid). Live = black: mean still
   rises above **0.3** (lift).
8. **Restart:** slot enabled 0 for 1 s, back to 1: the first read is the live picture (mean abs diff vs in1 < 0.01),
   stamp z small; no old trail pops in.
9. **Rate 2 + Shiftx 1 repeat:** over 3 s wall clock the picture moves **6 +- 1** px (2 generations/s), z still
   counts every cook; Hold on: two reads identical.
10. **Presets 1-5, 60 s each on the clip:** mean luma stays in **[0.03, 0.97]**, std > 0.01, no NaN; look as named
    (burn-in: brights stick and fade with Decay 0.97; acid: zoom spiral with hue cycling). Note Precision 8bit with
    small steps (Huestep < 0.5): the state stops changing (re-quantised every generation) - expected, record it.
11. **Cost** (out1 pulled, pane elsewhere, 120 frames): fx <= **1.0 ms** worst case (6 bilinear taps: Displace +
    filters), ~0.3 ms point-wise only; stamp ~0.05, outc ~0.05; project 60 fps, `cookRate` untouched.
12. Presets recall; captures; `td_checkpoint`, save, park, results here + T-entry.

## Not done / open
- JPEG block pass inside the loop: chain `dct` instead (no second DCT shader).
- No mask input (shared rack mask waits for the first module that needs it, fx_glitch.md).

## Verified live (26 Oct, 31550; scratch first, then main)
- Builds clean; `fx` is 16-bit float at Precision 16f.
- Exact passthrough: Amount 0, enabled 0, mix 0 -> max diff 0. Control (defaults, clip playing): max 0.58, mean 0.009.
- Identity holds (Leak 0): two `fx` reads apart identical (max 0) while in1 changed (mean 0.023).
- Exact shift (scratch, Leak 0, repeat, Shiftx 1): B == roll(A, zB - zA = 29) with max error 0.
- Crush 2 (Leak 0.1): out1 values only 0 / 85 / 170 / 255.
- Presets 1-5, 10 s each on the clip: mean luma 0.46 / 0.47 / 0.33 / 0.79 / 0.46, std 0.49 / 0.21 / 0.33 / 0.08 /
  0.21, no NaN, nothing locked.
- Restart (check 8): with the pane on the rack the bypassed tile kept the module cooking, so stamp z never reset
  (T-122 (4)); first read after re-enable was 0.008 mean off the live picture.
- Cost (preset 5 melt flow, 120 pulled cooks): 0.80 ms median (fx 0.42, outc 0.18, stamp 0.13), p90 1.44.
- Not run live: autogain target (check 7), Rate 2 motion (check 9).
