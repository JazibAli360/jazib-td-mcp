# fx_stylise: FX_stylise rack + modules (lane B, 27 Oct 2026, TD 2025.31550 target)

`/project1/lab/FX_stylise`. Image stylise filters used on a different layer from FX_film (BUILD_PLAN_27OCT s2: FX7a
FX_stylise + FX7c FX_paint + backlog #71 in one rack). Specs = research rows: SX-05 / SX-06 / SX-07
(`docs/research/FX7a_shadertoy_glsl_libraries.md`), 7C-01 / 02 / 04 / 05 / 09 (`FX7c_other_tools_effects.md`), #71
(`FX0_effects_backlog.md`). Order: outline (pilot) -> boil -> ink -> saber -> clean -> watercolour -> engrave -> kuwahara.

## Rack (`builders/fx_stylise.py`)
The FX_glitch rack reused as is (execs `builders/fx_glitch.py`, like `fx_analog.py`; no copy of the rack code): `slots`
table (name module enabled order mix), per slot module COMP -> `_mix` (Cross) -> `_slot` (Switch 0 bypass / 1 module / 2
mix), Panic, Input auto / live / test (stored webcam clip). Module X = `builders/fx_stylise_X.py` (template:
`docs/builds/fx_glitch.md` "Module template"). **Rest state: every slot enabled 0** (the rack passes in1 through).
Additions, each used by 2+ modules: Text DAT `palette_map_logic` (W1-B palette logic for the modules' `pal` CHOPs),
`H['pas']` (compute pass with size expressions + `npasses`), `H['glsl']` (read a shared shader from `builders/glsl/`).
```python
ns = dict(globals()); exec(open('<repo>/builders/fx_stylise.py').read(), ns)
ns['build']('/project1/lab')                               # rack + outline1 (enabled 0); idempotent
ns['add']('/project1/lab/FX_stylise', 'boil')               # boil1, wired last, enabled 0
ns['remove']('/project1/lab/FX_stylise', 'boil1')
```
Palette (W1-B, `docs/builds/palette_convention.md`): a module that colours things execs `builders/fx_stylise_pal.py`:
`Palette` page (Palsource: custom stops / file / the 8 stop presets / 20 Lospec presets; Palstops, Palfile, Palmode,
Palinterp, Palreverse, Palshift), Script CHOP `pal` (16 stops, recooks on palette edits) and `uPal` + `uPalCtl` on its
GLSL ops; shaders prepend `glsl/px_palette.glsl` and colour with `pxColSrc(uCs, solid, picture, attrT)` (Colsrc menu
solid / palette / attr / source / index, Palpos, Palspread, Keep).
Live checks helper: `builders/fx_stylise_checks.py` (solo / rest / still / diff / cost / fps / presets / module checks;
two execs per check).

## Module `outline` (`builders/fx_stylise_outline.py`; SX-06 + 7C-05; pilot)
Mirror: `builders/fx_stylise_outline_logic.py`. Tests: `test/test_fx_stylise_outline.py` (15, glslc of seed / jfa / fx).
`in1` -> `seed` (JFA size = in1 / Res; matte of the block's mean colour (one bilinear tap per 2x2); an inside texel next
to an outside one stores the linear Threshold crossing as a seed) -> `jfa` (**`builders/glsl/gen_sim_vor_jfa.glsl`
imported read-only**, GEN_sim untouched; its `uJ.z` = Pm = the passes the look needs: reach 2^Pm - 1 texels >= the
look's range (Width / 6 x Glow / Spacing x (Bands + 1) / Offset / Wobble, Pulse at its max so a beat never changes
the pass count; `Maxdist` overrides; contour with Bands 0 and the distance view = full frame), npasses = Pm + Extra:
outline 6 px = 5 passes instead of 11 at half res) -> `fx` (nearest seed of the 2x2 JFA texels around
the pixel -> distance in full px, sign from the full-res matte, Wobble noise, look, palette, Amount mix) -> `out_sel`
(Amount 0 = in1, nothing cooks) -> `out1`.

| Page | Pars |
|---|---|
| Outline | Amount, Mode (outline / halo / contour / sticker / distance view), Matte (luma / alpha / max rgb), Threshold, Invert, Res (full / half / quarter), Extra, Maxdist (0 = auto), Width, Offset (+ out), Soft, Intensity, Glow, Glowgain, Seed |
| Contour | Spacing, Bands (0 = endless), Fade (last N bands), Direction (out / in / both), Function (lines / saw / bounce / sine), Gap, Speed (bands / s), Phase (bind audio) |
| Look | Colsrc, Colr/g/b, Palpos, Palspread, Keep, Back + Inside (picture / dimmed / black / transparent), Backdim, Blend (over premultiplied / add), Wobble, Wobblescale, Wobblespeed, Pulse (bind a kick) + Pulsegain (scales width, glow, intensity), Hdr (rgba16float out) |
| Palette | W1-B (default neon_trio, cycle) |

attrT per mode: outline = across the line (0..1), halo = distance / (3 x Glow), contour = band index k (Colsrc index +
Palspread 1 = one stop per band), sticker = distance / Width. Over = premultiplied (rgb <= alpha with a transparent
back); Add = light, HDR with Hdr on. No limiter.
Presets (full state, T-124 (1)): 1 neon outline, 2 halo (quarter res), 3 contour echo (quarter), 4 sticker, 5 wobble
rings (quarter).
Offline: JFA vs brute force max err <= 1 texel on random disc mattes at half res (test); signed distance of a disc vs
the exact circle: mean 0.11 px, max 2.0 px at half res (only right at the edge: one seed per texel along it).
Words / names: a Text TOP of the whole word is the matte (never cut, memory rule).

### LIVE CHECKS (outline)
1. Builds clean (`td_errors` none); seed / jfa / fx compile; `jfa.par.npasses` = 5 for the default outline at half res
   (11 for the distance view).
2. Exact passthrough (clip paused on a real frame, img_src std > 0): Amount 0, slot enabled 0, mix 0, Panic -> max
   diff **0**.
3. JFA: `outline_jfa(m)`: GPU jfa == numpy mirror of the GPU seed map (share >= 0.999), vs brute force on 20 k sampled
   texels max err <= 1 texel.
4. Parity: `outline_parity(m)` for outline / halo / contour (Speed 0) / sticker, Colsrc solid, Wobble 0: over-tol share
   (2/255) < 0.5 %.
5. Palette: Colsrc index on contour: band k colour = stop k (read 3 band pixels).
6. Presets 1-5 recall full state; cost per preset <= ~3 ms (target 0.5-1.0); project fps with the rest parked.

### Verified live (outline: 27 Oct 2026, 31550, b4; load average ~28 with 4 other TDs building)
- Rack built by the builder (`build('/project1/lab')`), no errors / warnings in the module; JFA 540x960 at half res.
- Passthrough (clip paused on a real frame, img_src mean 0.468, std 0.228): Amount 0, slot enabled 0, mix 0, Panic ->
  max diff **0**; on: 69 % of pixels changed (preset 5 left on), 8 % for the default outline.
- JFA: GPU jfa == numpy mirror of the GPU seed map on **99.9994 %** of texels (11 full passes: 100 %); vs brute force at
  20 k sampled texels (within the reach): max err **0.15 texel** (target <= 1 px at half res).
- Parity vs `fx_stylise_outline_logic.reference(in1)` (Colsrc solid, Wobble 0, Speed 0): outline, halo (dim back),
  contour lines (Phase 0.3, 10 bands, black back), contour sine both-ways gap 0.2 add, sticker (quarter, transparent
  back), outline full res max-rgb inverted offset -6: over-tol (2/255) share **0 - 4e-6** (<= 9 pixels: seed positions
  differ by <= 0.56 texel where the GPU's bilinear block mean rounds differently), mean diff <= 5e-4.
- Palette: contour, Colsrc index, custom stops red / green / blue, steps: 240 k band-centre pixels, **100 %** = stop
  (k mod 3).
- Presets 1-5 recall the full state (45 pars, no mismatch). Cost (median per frame, own TOPs, In TOP excluded, 110
  frames, clip playing): neon outline **1.92 ms** (jfa 0.70 GPU, 5 passes; seed 0.33; fx 0.20), halo 2.67, contour echo
  1.74, sticker 2.15, wobble rings 2.22. First version (full 11-pass JFA, 20-fetch seed) was 3.4-5.4 ms. b4 real fps
  **60.25** (300 frames, cookRate 60 untouched). Rest: slot enabled 0, defaults.

### In main (outline: 27 Oct 2026, JazibTD_home.564)
NEW COMP `/project1/lab/FX_stylise` built by the builder in main (`build('/project1/lab')`, in a quiet minute: no heavy
exec in main / b3 / b5 / scratch logs for 60 s), placed in the lab plan's **FX racks** stage (`jz_stages` + `restage`:
ok, no overlaps / intruders), no errors. Re-check in main: parity over-tol 7e-6, JFA = mirror 99.9994 % (brute force
0.016 texel), Amount 0 and rest state diff **0**. Cost in main 5.5-8.1 ms median (jfa GPU 3.4-4.1 ms) at load average
37-53 with every side TD busy: not a fair number (same shader on b4 1.9 ms); main real fps 61.0 while it ran. Rest: slot
enabled 0, **parked**, saved.

## Module `boil` (`builders/fx_stylise_boil.py`; 7C-01 line boil / animated on twos)
Mirror: `builders/fx_stylise_boil_logic.py`; shared GLSL + numpy hash / noise / bilinear: `builders/fx_stylise_lib.py`.
Tests: `test/test_fx_stylise_boil.py` (10, glslc of stamp / hold / fx); shared test helpers `test/fx_stylise_testkit.py`.
`in1` -> `stamp` (1x1 in place: tick = floor(t x Holdfps), time of the last tick change, last cook) -> `hold` (in place:
copies in1 only on a tick frame; first cook / > 0.25 s gap count as a tick) -> `hsrc` (Holdfps 0 = live in1, hold not
pulled) -> `fx` (boil offset = Boil x value noise at Boilscale, seed = tick mod Boilframes; Sobel ink of the held luma at
the boiled position, taps Linewidth px apart; fill at a Fillboil share of the offset: posterise Levels / paper / picture
/ palette by luma; paper grain; ink colour; Amount mix with the live in1) -> `out_sel` -> `out1`.
Pars: Boil page Amount, Holdfps (12 = on twos, 8 = threes, 0 = no hold), Boil, Boilscale, Boilframes, Fillboil,
Linewidth, Edgethr, Edgesoft, Inkamount, Seed; Fill page Fill, Levels, Ink rgb, Paper (grain), Grainscale, Paper rgb;
Palette page (Fill palette). Presets: 1 on twos, 2 sketch (paper line art, threes), 3 jittery ink (picture + heavy
ink), 4 poster boil (palette fill, 6 fps), 5 smooth 60 (no hold, slow boil).

### LIVE CHECKS (boil)
1. Builds clean; stamp / hold / fx compile.
2. Passthrough (clip paused, img_src std > 0): Amount 0, slot enabled 0, mix 0, Panic -> **0**.
3. Parity: clip paused, Holdfps 0.1 (tick fixed for 10 s), each Fill except palette: `boil_parity(m)` over-tol < 0.5 %.
4. Hold: clip playing, Holdfps 8: `boil_hold` over 120 frames -> distinct ticks 16 +- 1; Holdfps 12 -> 24 +- 1.
5. Presets 1-5 full state; cost <= ~3 ms (estimate 0.3-0.5 ms); fps.

## Module `ink` (`builders/fx_stylise_ink.py`; SX-07 XDoG pen-and-ink, toon, comic)
Mirror: `builders/fx_stylise_ink_logic.py`. Tests: `test/test_fx_stylise_ink.py` (7, glslc of blurh / blurv / fx).
`in1` -> `blurh` -> `blurv` (separable Gaussians of luma at Sigma and K x Sigma, exact normalised weights, radius
ceil(3 K Sigma) <= 48 px, constant loop bound; rgba16float) -> `fx` (XDoG S = (1 + p) G_s - p G_ks, E = 1 if S >= Eps
else 1 + tanh(Phi (S - Eps)); xdog: paper / picture / palette-by-E fill under ink (1 - E); toon: Bands soft luma bands
x hue (Saturation) or palette, ink lines from the same E; comic: toon + halftone dots below Dotthr on a Dotangle screen
of Dotsize cells, Dotjitter) -> `out_sel` -> `out1`.
Pars: Ink page Amount, Mode, Sigma, K, Sharpen, Eps, Phi, Inkamount, Fill, Seed; Toon page Bands, Bandsoft,
Saturation, Toonpal, Dotsize, Dotangle, Dotthr, Dotjitter; Colour page Ink / Paper rgb; Palette page.
Presets: 1 pen and ink, 2 woodcut, 3 cel shade, 4 comic, 5 neon pastel (palette by E, no ink colour).

### LIVE CHECKS (ink)
1. Builds clean; blurh / blurv / fx compile.
2. Passthrough (clip paused, std > 0): Amount 0, slot enabled 0, mix 0, Panic -> **0**.
3. `ink_parity(m)` for xdog paper, xdog picture, toon, comic: blur vs mirror <= 2e-3 (16F), look over-tol < 0.5 %.
4. Presets 1-5 full state; cost <= ~3 ms (estimate 0.4-0.8 ms); fps.

### Verified live (ink: 27 Oct 2026, 31550, b4; load average 50-65)
- Added by the builder (`add`, 7 wires), no errors. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `ink_parity`: blur vs mirror max 9.8e-4 (16F store); look over-tol **0** (max 2e-3) for xdog paper, xdog picture
  (woodcut pars), toon, comic (jitter 0.3).
- Presets 1-5 full state (29 pars). Cost median: pen and ink **1.41 ms** (blurh 0.17 + blurv 0.24 + fx 0.13 GPU),
  woodcut (sigma 2.2) 2.03, cel 2.11, comic 2.12, neon pastel 1.72; first version (97-iteration loop with 2 exp per
  tap) 2.5-3.0 ms (blurs ~1 ms each): the centre-out incremental Gaussian (two multiplies per tap pair, runtime
  break under the constant bound) cut the blurs 4x. b4 60.55 fps.

### Verified live (boil: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `boil_parity` (clip paused, Holdfps 0.1): posterise over-tol 0.11 % (one posterise level at rounding ties: GPU
  bilinear vs float64), paper 6e-5, picture (Boil 6, Linewidth 2.5) 8e-6, Holdfps 0 posterise 0.11 %.
- Hold clock (clip playing, 120 frames): Holdfps 8 -> 17 distinct ticks, 12 -> 25 (expected 16 / 24 + the partial
  first tick).
- Presets 1-5 full state (26 pars). Cost median: on twos **0.87 ms** (fx 0.22 GPU, hold 0.05, stamp 0.04), sketch 0.99,
  jittery ink 0.89, poster boil 1.28, smooth 60 0.49. b4 60.1 fps boil on / 60.3 at rest.

## Module `saber` (`builders/fx_stylise_saber.py`; 7C-09 energy beam on paths / text / masks)
Mirror: `builders/fx_stylise_saber_logic.py`. Tests: `test/test_fx_stylise_saber.py` (7, glslc of seed / jfa / fx; the
segs callback == the mirror's `pts`). Reuses the outline module's `SEED` shader and JFA wiring (exec'd read-only) and
GEN_sim's `gen_sim_vor_jfa.glsl`.
Sources: **path** = Table DAT `path` (or `Pathdat`, a DAT path): rows `x y` in uv (0..1 of the frame) or px, a row `-`
= pen up, <= 64 points -> Script CHOP `segs` (x y u pen, u = arc length 0..1) -> uniform array `uPts[64]`; capsule
distance per segment, draw-on Start..End along u, a hot Tip at End. **mask** (matte of in1) / **masktop** (Masktop TOP,
fitted to in1 by `mfit`: a Text TOP of a whole word, a logo, a person matte) -> seed + JFA (Pm from the glow reach)
-> distance to the edge (+ Offset; Solid = inside counts as 0), draw-on around Revcentre (angle) or along Wipeangle.
Light: core 1 / (1 + (d / Corewidth)^Corepow) x Core rgb + (Glowint (Bias e^(-d / Glow) + (1 - Bias) e^(-d / (Glow x
Spread))) + Tip e^(-tipd / Glow)) x glow colour (solid or palette along u), x Intensity x flicker (Flicker, Flickerhz,
per Seed), Distort = value-noise warp of d; added over Back (picture / dim / black / transparent).
Presets: 1 blue saber (the star path), 2 red sith (distort + flicker), 3 neon sign (Masktop), 4 draw on (palette along
the path, End 0.6, tip), 5 person aura (matte of in1, offset 6 px, quarter res).

### LIVE CHECKS (saber)
1. Builds clean; seed / jfa / fx compile; `segs` 64 samples; path default = 11 points.
2. Passthrough: Amount 0, slot enabled 0, mix 0, Panic -> **0**.
3. `saber_parity(m)` (Distort 0, Flicker 0): path full, path End 0.5 (tip), mask (luma of in1), masktop (a Text TOP of
   a whole word): over-tol < 0.5 %.
4. Presets 1-5; cost <= ~3 ms (estimate 0.5-0.9); fps.

### Verified live (saber: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors; `segs` = 11 points (default star). Passthrough: Amount 0 / enabled 0 / mix 0 / Panic
  -> **0**.
- `saber_parity` (Distort 0, Flicker 0): path full over-tol **0** (max 2e-3); path End 0.5 + Tip 3 on black **0**;
  mask (luma of the clip, Offset 4) 2e-5 (JFA seed rounding as outline); masktop = a Text TOP 'SABER' (whole word,
  alpha matte, Solid, dim back) **0**. The test Text TOP was removed in its own exec (T-119 (5)).
- Presets 1-5 full state (47 pars). Cost median: blue saber **0.93 ms** (fx 0.59 GPU, 10 capsules), red sith 0.73,
  neon sign (mask, 9 JFA passes at half res) 2.87, draw on 1.09, person aura (quarter) 1.60. b4 60.4 fps.

## Module `clean` (`builders/fx_stylise_clean.py`; SX-05 edge-preserving clean / beauty + despeckle)
Mirror: `builders/fx_stylise_clean_logic.py`. Tests: `test/test_fx_stylise_clean.py` (6, glslc; the shader's 19-exchange
network == np.median on 2000 random 9-sets).
`in1` -> `med` (3x3 median per channel; Median off: `msrc` = in1, not pulled) -> `bilh` -> `bilv` (separable bilateral:
w = exp(-(i^2 / 2 Sigma^2 + |c_i - c_0|^2 / 2 Edge^2)), Radius <= 24 (runtime break under the constant bound), range
on rgb or luma (Rangemode); bilv mixes with in1 by Amount and adds Detail x (in1 - smooth)) -> `out_sel` -> `out1`.
Presets: 1 beauty (R 6, Edge 0.08, Detail 0.15), 2 despeckle (median + R 2), 3 flat cartoon (R 12, Edge 0.15), 4
pre-glitch (median + R 3, Edge 0.04: put it before FX_glitch datamosh / pixel sort), 5 plastic (R 20 luma range).

### LIVE CHECKS (clean)
1. Builds clean; med / bilh / bilv compile.
2. Passthrough: Amount 0, slot enabled 0, mix 0, Panic -> **0**.
3. `clean_parity(m)` per preset 1-5: over-tol < 0.5 % (16F intermediate); report the high-frequency std (hf) in / out.
4. Presets 1-5; cost <= ~3 ms (estimate 0.6-1.5); fps.

### Verified live (clean: 27 Oct 2026, 31550, b4)
- First build: `bilh` failed to compile (a warning, not an error, on 31550): the shared bilateral text indexed
  `sTD2DInputs[1]` in a branch only the 2-input `bilv` takes; the 1-input `bilh` has `sTD2DInputs[1]` out of range
  (T-177). Fixed by a `#define FINAL` variant for bilv; offline glslc now sizes the stub per pass (`NIN`) for every
  FX_stylise module.
- Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**. `clean_parity` presets 1-5: over-tol **0** (max 1.3e-3,
  16F intermediate). High-frequency std of the paused clip 0.0050 -> despeckle 0.0046, pre-glitch 0.0047, plastic
  0.0010; beauty 0.0055 (Detail 0.15 adds back) and flat cartoon 0.0066 (flat regions with sharper steps).
- Presets full state (8 pars). Cost median: beauty **0.79 ms**, despeckle 0.82, flat cartoon 1.55, pre-glitch 0.90,
  plastic (R 20) 2.03. b4 59.95 fps.

### In main (boil, ink, saber: 27 Oct 2026)
Added by the builder one module per exec (un-park, `add`, check, rest, park, save), each in a quiet minute: boil
JazibTD_home.592 (parity over-tol 0.11 %, Holdfps 0.1), ink .594 (blur 9.8e-4, over-tol 0), saber .596 (path parity
over-tol 0); rest diff 0, parked.

## Module `watercolour` (`builders/fx_stylise_watercolour.py`; 7C-02 watercolour wash)
Mirror: `builders/fx_stylise_watercolour_logic.py`. Tests: `test/test_fx_stylise_watercolour.py` (5, glslc).
`in1` -> `wash` (at Res, half default, rgba16float: luma gradient direction (Flow bleed = across edges, flow = along
them) bent by value noise (Wobble, Wobblescale), Taps tent-weighted bilinear samples over +- Spread px) -> `look` (full
res: bilinear wash; wet-edge rim = |grad luma(wash)| x Edgedark; density = pigment noise (Pigment, Pigmentscale) x
2-octave paper grain (Granulation, Grainscale) x (1 + 0.6 rim); colour = paper - (paper - wash) x density (or palette
by luma, Saturation); luma above Whitethr fades to paper) -> `out_sel` -> `out1`.
Presets: 1 wash, 2 wet bleed, 3 dry brush (flow, heavy wobble + grain), 4 pastel palette, 5 ink wash (grey, dark rims).

### LIVE CHECKS (watercolour)
1. Builds clean; wash / look compile.
2. Passthrough: Amount 0, slot enabled 0, mix 0, Panic -> **0**.
3. `watercolour_parity(m)` for presets 1, 3, 5: wash vs mirror over-tol < 0.5 % (16F + GPU bilinear), look over-tol
   < 0.5 %.
4. Presets 1-5; cost <= ~3 ms (estimate 0.8-1.5); fps.

### Verified live (watercolour: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `watercolour_parity` presets 1, 3, 5: wash vs mirror max 6.2e-4 (over-tol 0), look over-tol **0** (max 3.2e-3).
- Presets full state (24 pars). Cost median: wash **0.68 ms**, wet bleed 0.73, dry brush 0.70, pastel palette 0.84,
  ink wash 0.63. b4 60.5 fps.

## Module `engrave` (`builders/fx_stylise_engrave.py`; 7C-04 engraving / banknote line screen)
Mirror: `builders/fx_stylise_engrave_logic.py`. Tests: `test/test_fx_stylise_engrave.py` (5, glslc).
One compute pass: smoothed luma Lb (5 bilinear taps at Smooth px); line coordinate v = across the lines (Angle) + Bend x
Spacing x Lb (lines bend with tone) + Wave x sin(2 pi (along x Wavefreq + 0.137 Seed)) (guilloche) + Speed drift;
half-width = Width x (1 - Lb)^Gamma x Spacing / 2, antialiased over Aa px (hairlines fade at white); a Cross set at
Angle + Crossangle below Cross luma; ink (colour or the picture's colour) over paper / picture / palette by luma.
Presets: 1 etching, 2 banknote (guilloche wave), 3 woodcut lines, 4 neon scan (palette, drifting), 5 colour lines
(picture-coloured lines on black).

### LIVE CHECKS (engrave)
1. Builds clean; fx compiles. 2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `engrave_parity(m)` for presets 1, 2, 3, 5: over-tol < 0.5 %. 4. Presets 1-5; cost <= ~3 ms (estimate 0.3); fps.

### Verified live (engrave: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `engrave_parity` presets 1, 2, 3, 5: over-tol **0** (max 2.5e-3).
- Presets full state (27 pars). Cost median 0.40-0.45 ms (fx 0.07-0.14 GPU). b4 60.8 fps.

## Module `kuwahara` (`builders/fx_stylise_kuwahara.py`; FX0 #71 anisotropic Kuwahara / oil paint)
Mirror: `builders/fx_stylise_kuwahara_logic.py`. Tests: `test/test_fx_stylise_kuwahara.py` (5, glslc).
`in1` -> `tens` (structure tensor at Res: rgb Sobel from bilinear taps Res px apart, E F G) -> `tblur` (5x5 Gaussian)
-> `kuw` (eigenvector orientation + anisotropy A x Anisotropy; ellipse Radius x (Alpha + A) / Alpha by Radius x Alpha /
(Alpha + A) (each clamped 0.1-2 x Radius) rotated to the edge, loops over its rotated bounding box (runtime break under
a constant bound); 8 sectors with the polynomial weights (Zeta = 2 / Radius by default, Zerocross) x Gaussian falloff;
sector mean + variance; output = sum of means x 1 / (1 + (1000 var)^(Sharpness / 2))) -> `fx` (bilinear up to full
res, Amount mix) -> `out_sel` -> `out1`.
Defaults: quarter res, Radius 3 texels (= 12 px at 1080x1920). Presets: 1 oil paint, 2 brush strokes (Alpha 0.35:
stretched), 3 watercolour blobs (isotropic, R 4), 4 fine detail (half res, R 2), 5 poster (R 5, Sharpness 16).

### LIVE CHECKS (kuwahara)
1. Builds clean; tens / tblur / kuw / fx compile.
2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `kuwahara_parity(m)` presets 1, 2, 3: tensor relative max < 1e-2 (16F), kuw window (48 x 48 texels) over-tol
   < 0.5 % (16F tensor + GPU bilinear), out1 vs up(in1, kuw) over-tol < 0.5 %.
4. Presets 1-5; cost <= ~3 ms (estimate 1-3 ms at half res); fps.

### Verified live (kuwahara: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `kuwahara_parity` presets 1-3: tensor relative max 1.0e-3 (16F); kuw on a 48 x 48 texel window over-tol 0 / 0 /
  4e-4 (one texel: 16F tensor near an isotropic point); out1 vs up(in1, kuw) over-tol **0**.
- **Cost, first version: 6-33 ms** (half res R 5: kuw 8.1 ms GPU; full res R 4: 32 ms): far over budget. Kernel
  rewritten (sector weights as two vec4, eight named accumulators instead of per-thread m[8] / s[8] / w[8] arrays,
  T-145) and the defaults moved to quarter res with smaller texel radii (same screen size): oil paint **1.37 ms** (kuw
  0.63 GPU), brush strokes 1.42, watercolour blobs 1.38, fine detail (half R 2) 2.19, poster (R 5) 2.59. Parity
  unchanged after the rewrite. b4 60.6 fps. On the smooth webcam clip the default changes little (mean 0.4 %); the
  look shows on textured footage and bigger radii (no limit on Radius / Res).

### In main (watercolour, engrave, kuwahara) + library
watercolour JazibTD_home.608, engrave .612, kuwahara .620 (by builder, quiet minute, parity over-tol 0, parked). All
8 modules in main at rest (slots enabled 0). Library: `library/FX_stylise/` 0.1.0 (613 KB .tox).

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.746).
