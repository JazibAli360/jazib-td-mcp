# fx_analog_plasma: FX_analog module `plasma` (FX2 AV-15, FX0 row 78; offline 26 Oct 2026, TD 2025.31550 target)

Status: **live on b3 + main (26 Oct, 31550), slot `plasma1` (enabled 0).** Everything under LIVE CHECKS needs 31550. Rack +
template: `docs/builds/fx_glitch.md` (FX_analog = the same rack, `builders/fx_analog.py`; nothing to register, the
rack finds `builders/fx_analog_plasma.py` by name). The small-display half of row 78 (LCD / VFD / Nixie / flip-dot /
e-ink) already lives in `FX_retro.smalldisplay`; this module is the plasma panel only.

Files: `builders/fx_analog_plasma.py` (module), `builders/fx_analog_plasma_logic.py` (numpy mirror of both passes:
`reference`, `est_step`, `compare`, `pars_from_comp`), `test/test_fx_analog_plasma.py` (26 tests incl. glslc of both
passes against TD stubs).

## What it does
A plasma panel (PDP) makes each 8-bit level from time-sliced **sub-fields**: binary weights 1, 2, 4 ... 128 lit or
dark inside one frame. A still picture integrates to the right level. When the eye **tracks** a moving picture it
collects sub-field k from the pixel at `p + v (t_k - 0.5)` (t_k = the sub-field's time centre in the frame), so where a
moving gradient crosses a sub-field boundary (127 -> 128: every bit flips) the sum jumps: bright or dark, often
coloured **false contours** that move with the picture. Real panels reduce it with more, smaller MSB sub-fields
(10-12 sub-fields), which the Subfields menu offers.

## Network
`in1` -> `est` (Motion = estimate only; compute rgba32float **in place**, one texel per Estres cell: xy = motion in
full px per cook, z = cell luma, w = last cook time) / `mv_zero` (1x1) -> `mv_src` (Switch) -> `fx` (one compute
pass, `inputextenduv hold`) -> `out_sel` (Switch: Amount 0 = `in1`, nothing else cooks) -> `out1`. 2 inputs on the
fx GLSL TOP (T-88 limit 3).

**est** (no optical flow op on macOS, T-18): normal flow per cell from the previous cook's cell luma,
`v = -(L - L_prev) grad L / (|grad L|^2 + Eps) * Estres`, cell luma = mean of a 4 x 4 texel grid, noise gate
Minmotion px, temporal Smooth. A second cook in the same frame changes nothing; a gap > 0.25 s (bypass, panic,
parked) or the first cook restarts at v = 0. Good for motions up to about one cell per frame.

**fx**: per pixel, for each sub-field k (time order ascending or descending, each slot = Address + weight): read the
code (`floor(255 x^Gamma + dither + 0.5)`) at the tracked pixel (texelFetch, clamped; consecutive sub-fields that hit
the same pixel reuse its split), split it greedily (largest weight first) into lit sub-fields, add weight k if lit.
Sum / 255, `^(1/Gamma)`. Green can be read at `t_k + Greenlag` (slow green phosphor: green fringes behind moving
edges). Cells multiplies an RGB stripe + horizontal rib mask. Amount mixes with the input.

## Pars
| Page | Par | What |
|---|---|---|
| Plasma | Amount | 0 = in1 exact (out_sel), 1 = full |
| | Subfields | binary8 (1..128, strongest), pdp10 (1..32 + 4 x 48), pdp12 (1..16, 24, 5 x 32, 40) |
| | Order | ascending / descending weights in time |
| | Address | address/reset time per sub-field slot, in weight units (spreads the time centres) |
| | Gamma | panel gamma: codes in linear light (2.2 = real panel, contours in darks; 1 = codes = input) |
| | Motion | Vector (Motion x/y), Sweep (vector x sin(2 pi t / Period): breathing contours on a still picture), Estimate (est field x Gain, + the vector) |
| | Motionx, Motiony | px per cook (y up) |
| | Period | sweep period s |
| | Seed | dither noise seed |
| Estimate | Gain, Estres, Eps, Minmotion, Smooth | est field gain, cell px, flat-area damping, noise gate px, temporal smoothing |
| Look | Dither | code-unit noise per pixel and frame (PDP dark-level dither) |
| | Greenlag | green sub-fields read later by this many frames (+ = trailing) |
| | Cells, Cellsize | RGB stripe + rib mask strength, cell px |

No clamps beyond slider ranges (user rule); `max(Cellsize, 1)` / `max(Period, 1e-3)` only avoid a division by 0.

Presets: 1 **pan contour** (binary8, vector 6 px/frame), 2 **sweep** (binary8, 10 px x sine, 2 s), 3 **real pdp**
(pdp10, estimate x 1.5, dither 0.6, green lag 0.15, cells 0.25), 4 **heavy** (binary8 descending, estimate x 3, green
lag 0.3), 5 **plasma wall** (pdp12, vector (3, 2), cells 0.5 at 9 px).

## Perf lane 2 (27 Oct, b2, 31550)
- New pass `codes` (compute, rgba32float, picture size): Gamma + dither + sub-field split once per pixel -> masks r, g, b.
  `fx` (in0 picture, in1 motion, in2 codes) reads the masks at the tracked positions instead of re-coding every
  sub-field's source pixel; `lit()` is a closed form of the greedy split (offline test: same mask for every code 0..255,
  all 3 tables); t_k inline (no per-thread array, T-187).
- Paired same-frame A/B (old fx vs codes + new fx, T-145): total 0.63-0.80x, fx GPU 0.36x; closed form alone 0.87x;
  an 8-bit codes variant 0.88x (dropped). Module solo b2: see PERF_QUIET_27OCT.md "Perf lane 2".
- Parity after `upgrade` on b2 (clip paused, vector Motionx 8, Greenlag 0.3): binary8 Gamma 1, pdp10 / pdp12 Gamma 2.2,
  desc and asc: `max_codes` 0, `frac_any` 0 (bit-exact); Amount 0 -> 0.

## Cost estimate (not measured)
fx: 8-12 sub-fields x (1-2 texelFetch + greedy split <= 12 steps x 3 channels, skipped when the tracked pixel repeats)
at 1080x1920: ~0.6-1.5 ms GPU. est (135 x 240 cells x 80 fetches): ~0.05 ms. Expected total <= ~1.5 ms; budget 3 ms.

## Offline numbers (numpy, `reference`)
Ramp 0.2-0.8 across 96 px, Motion x 8, Gamma 1: mean abs error binary8 0.046, pdp10 0.034, pdp12 0.033; at the
127/128 boundary binary8 shows codes 117 -> **251** -> 248 -> 186 (the classic bright false contour). Flat fields and
motion along the gradient's level lines stay exact; static picture at Gamma 1 = input exactly (all three tables).

## LIVE CHECKS (~15 min, b3; reads in a SEPARATE exec from any par change, T-74; clip paused for 1-4)
1. **Builds clean:** `ns['add']('/project1/lab/FX_analog', 'plasma')`; `td_errors` none on `plasma1/est`, `plasma1/fx`.
2. **Exact passthrough:** Amount 0 -> out1 vs FX_analog img_src max diff **0**; slot enabled 0 / mix 0 / Panic -> 0.
   Static check: Amount 1, Motion x 0, Motion y 0, Gamma 1, Dither 0, Cells 0 -> max diff **0** (codes = input).
3. **Reference parity (vector mode):** set Motion vector, Motionx 8, Gamma 1, Dither 0, Greenlag 0.3, Cells 0; wait 4
   frames; then in a new exec:
   ```python
   L = {}; exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_analog_plasma_logic.py').read(), L)
   m = op('/project1/lab/FX_analog/plasma1')
   ref = L['reference'](m.op('in1').numpyArray(), L['pars_from_comp'](m))
   print(L['compare'](m.op('out1').numpyArray(), ref))
   ```
   Pass: `max_codes` 0 (allow <= 1 code on `frac_off` < 1e-3 from FMA rounding of `pc + v t` at exact pixel edges).
   Repeat with Gamma 2.2 and Subfields pdp10 / pdp12 (pow rounding: `frac_any` < 1e-3, max may hit one sub-field
   weight on those few pixels). Dither > 0 needs `frame=absTime.frame` of the cook: skip unless the clip is paused and
   the frame is pinned (not required).
4. **Contour present:** with check 3's pars, `frac_any` of out1 vs in1 > 0 and the out1 luma row across a smooth
   gradient is non-monotonic (capture one).
5. **Estimate:** Motion estimate, Gain 1, clip **paused**: after >= 10 cooks read `est` (separate exec; T-117 state
   re-cooks on read): |xy| max < 0.01 (static -> no motion). Clip **playing**: est has cells with |v| > 0.5 px where the
   picture moves; out1 differs from in1 mostly where motion and gradients meet. Re-enable after a > 0.25 s bypass: first
   est read = zeros in xy.
6. **Presets:** zkit Recall 1-5 set the stored pars exactly; each preset's out1 differs from in1 (playing clip).
7. **Cost:** out1 pulled per frame, sum cpu + gpu of plasma1's TOPs over 120 frames, median: pan contour and real pdp
   each <= ~3 ms (expect ~1-1.5); project fps with the rest parked (onFrameStart counter, T-124 (4)).

## Verified live (26 Oct, 31550; b3 then main)
- b3 (FX_analog loaded by tox from main, other slots enabled 0): `add` -> `plasma1`, td_errors none.
- **First pass ran on a black frame** (paused clip never decoded: all checks passed as identity vs identity, T-157 (3));
  redone after playing the clip for a second (img mean 0.469, std 0.228). Results below are on that frame.
- Exact passthrough: Amount 0 / slot enabled 0 / mix 0 / Panic -> **0**; Amount 1, no motion, Gamma 1 -> **0**.
- Parity (vector, Motionx 8, Greenlag 0.3, Dither 0, Cells 0): binary8 Gamma 1, pdp10 Gamma 2.2, pdp12 Gamma 2.2 ->
  `max_codes` **0**, `frac_any` 0 (bit-exact) while 95-96.5 % of pixels differ from the input.
- Estimate: clip paused -> est |xy| max 0.0; playing -> 4.1 % of cells > 0.5 px (max 3.5 px).
- Presets 1-5 recall exactly (stored rows match; see T-157 (1): the FIRST Recall right after the add applied nothing,
  the second did) and each changes the picture (42-100 % of pixels).
- Cost (median per frame, own TOPs, In TOP excluded, 120 frames): pan contour 1.39 ms, real pdp 1.63 ms. b3 real rate
  59.3 frames/s with plasma on vs 60.0 parked (onFrameStart counter). `est` first compile in estimate mode: one 319 ms
  CPU frame (one-off).
- Gamma != 1 re-quantises codes, so with Gamma 2.2 nearly every pixel differs by >= 1 code even without motion (look,
  not a bug).
- **Main** (JazibTD_home.462): slot `plasma1` (order 6, enabled 0), 1930 ops = b3, td_errors none; parity again
  `max_codes` 0 (86.5 % of pixels changed); pars restored to defaults; FX_analog parked.
