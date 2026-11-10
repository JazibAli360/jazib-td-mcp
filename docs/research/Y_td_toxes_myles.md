# Y. TD-Toxes (Aaron Myles Pereira): static study and audit of 11 `.tox` files (26 Oct 2026)

Research agent Y, 26 Oct 2026. Guardrails obeyed: **nothing was loaded into TouchDesigner, no `jazib-td` tool was used, no Python/GLSL
from the files was run.** The files were treated as untrusted data. Read only with `toeexpand` (TD 2's own helper, PLATFORM.md 1.1)
on copies in a scratch folder (one empty folder per tox), then `cat`/`grep`. A small text-only checker (`python3 -I`, never
`import`s or `exec`s anything from the files) compared every operator type and every non-custom parameter name against
`ops/INDEX_2025.31550.json`. Scratch deleted at the end. Everything below is **static reading (verification level: read, not run)**;
what the effects look like is inferred from the networks plus the README and has never been seen on this Mac.

Source: https://github.com/aaronmylespereira/TD-Toxes, commit `af4697dc9b61d7c29e1d3c4a13501dfe2c819ec8`, MIT (c) 2024 Aaron Myles Pereira.
Local: `jazib-td-mcp/research_src/TD-Toxes/` (git-ignored). Tags: `[FS]` read from the expanded files, `[DUMP]` the 31550 op index,
`[OH]` offline help in the app, `[L:T-nn]` jazib-td-mcp LEARNINGS.

## 0. Summary

- **The brief said 12 `*_MYLES.tox`; the repo has 11.** The README documents 9 of them (Abstract Fluid, Circuit Bending, Datamosh,
  Falling Liquid, Feedback, Pixel Sorting, Random Number, Random Rectangle Composite, Reaction Diffusion). `randomVideoFile` and
  `simpleFeedback` have no README entry. All files are tiny (0.7 to 5.4 KB).
- **Safe to load: all 11, yes.** No file has a script that does anything but set a local op's bypass/state; there is **no GLSL
  anywhere**, no `os`/`subprocess`/socket/URL code, no `import`. The only code that runs on load is TouchDesigner's *own* stock Palette
  `DocsHelper` extension (inside the embedded Palette `sharpen` and `feedbackEdge`), which is not in these files (it is
  `op.TDResources.mod.DocsHelper`). Load each into a scratch COMP, not into the home rig (section 12).
- **Every op type exists in 2025.31550** (checked all, incl. `inside`, `lumablur`, `slope`, `topto`, `remap`, `reorder`) and every
  non-custom parameter name exists too, except one possible rename (Trigger CHOP pulse, section 9).
- **All were saved on macOS** (14.4.1 / 14.5) with **build 2023.11600** (feedback: 2023.11760), Apr to Jun 2024. The README confirms
  2023.11600. So no Windows-only content. Two Palette parts inside them were saved at 2023.11225. They are two years older than our
  2025.31550 and were never opened here: a load can change defaults (verify with `td_custom_pars` / `td_errors`).
- **Not 1080x1920-ready.** Most follow their input size (good). `reactionDiffusion` is a generator with a `Resolution` custom par
  defaulting to **1920x1080** (landscape). `fallingLiquid`, `abstractFluid`, `circuitBending` derive sizes from the input.
  Several loops run in **32-bit float** (rgba32float) which is 33 MB per texture at 1080x1920.
- **Dangling references that will show red error flags on load** (author's project): `op('keyboardin1')['k1']` (4 places),
  `op('null2')['chan1']`, `op('select1')['ch1n76']`; stored input wires to `particlesGpu/out1`, `ndiin1`, `videodevin1`, `fit1`,
  `circuitBending/out1`, `dataMosh/out1`, `pulse1`; and a hard-coded author path in `randomVideoFile`.
- **No multi-pass GLSL**, so T-46/T-47 (pixel-mode multi-pass tearing) does not apply as written. But the feedback chains here are
  long native-TOP chains and T-46 says "feedback loops amplify it": test every one for torn frames before trusting (section 11).
- **Licence caveat for our ledger:** the repo is MIT, but 8 of the 9 documented networks are the author's re-builds of other people's
  free YouTube tutorials (Daniel Steenhoff, Elekktronaut, Paketa12, pppanik, Ben Heim) with no licence stated for those networks.
  Treat these as **study material and rebuild natively**; do not ship the tox files themselves in PF26 content.
- **Ranking for LED content (section 13):** 1 abstractFluid, 2 reactionDiffusion, 3 feedback (as a stage template), 4 fallingLiquid,
  5 circuitBending, 6 dataMosh, 7 pixelSorting, then the three helpers.

## 1. Common structure (all 11)

- Each tox root is a `base` COMP with `In`/`Out` TOP (or CHOP for `randomNumber`), `enableexternaltox off`, and a custom page
  (named "Parameters", "Custom" or "Parameter") that carries the README controls. [FS]
- **Pattern worth copying:** every custom par is wired to the internals by **bind expressions** (`parent().par.X`), so the tox can be
  driven from outside; `Reset` is a Pulse par bound to the Feedback TOP's `resetpulse`; `Dry/Wet` is a Cross TOP whose `cross` is
  bound to `Drywet`, with input 0 = clean and input 1 = processed (so `Drywet 0` = bypass).
- Pars are saved as `name flags value [expression] [bind expression]`. Flags `0x203` = bound; `0x1x` bit = expression mode.
  The four `keyboardin1` resets carry flag `...213`, i.e. the expression is the active mode and the bind is second.
- Custom par ranges below are decoded from the `.cparm` line (default = last number; the slider range is best effort, treat as
  approximate). Verify live with `td_custom_pars`.
- Embedded Palette parts: `sharpen` v1.0.2 (circuitBending, reactionDiffusion) and `feedbackEdge` v8.0.4 (abstractFluid,
  reactionDiffusion). Both exist in this install: `Samples/Palette/ImageFilters/{sharpen,feedbackEdge}.tox` [FS]. Each carries a
  Palette fallback input (`Movie File In` of `app.samplesFolder + '/Map/Jellybeans.1.jpg'` or `/Map/Nature/Movie.2.mp4`;
  both files exist on this Mac, read-only) and a `docsHelper` container.

## 2. simpleFeedback_MYLES (undocumented in README)

- **Visual:** the plainest video-feedback trail: each frame is the new frame composited over a faded copy of the previous output.
- **Chain:** `in1 -> comp1(over)[in1 = input 1]`; `feedback1(top=comp1) -> level1(opacity) -> comp1 input 0`; `comp1 -> out1`.
  Loop: comp1 -> feedback1 -> level1 -> comp1 (input 0). Note the Composite TOP's input order here: level1 (old) is input 0,
  `in1` (new) is input 1.
- **Custom par:** `Opacity` (float, default 0, saved 0.888) bound to `level1.opacity`. No Reset, no Dry/Wet.
- **GLSL/Python:** none. **External:** none. Stored input wire `particlesGpu/out1` (author's project, ignored).
- **Resolution:** follows the input; Feedback TOP keeps its own size cache (1920x1080 in the file's cache, not a setting).
- **Use as a lesson:** minimum feedback loop; confirms the pattern Feedback TOP (`top` = the loop's end) + Level for decay.

## 3. feedback_MYLES (README: "an implementation of feedback, created by me")

- **Visual:** trails with controllable zoom/drift/brightness/opacity per frame, blended with the clean signal.
- **Chain:** `in1 -> fit1(Resolution TOP) -> fbStart(null)`; `fbStart -> feedback1(top=comp1)`; loop
  `feedback1 -> transform1 -> level1 -> comp1(over)[input 0 = level1, input 1 = fbStart]`; `cross1[in1 | comp1] -> out1`.
- **Key pars:** transform1 `tx,ty` <- `Translate1/2`, `sx,sy` <- `Scale1/2`; level1 `brightness1` <- `Brightness`, `opacity` <- `Opacity`;
  cross `cross` <- `Drywet`; feedback `resetpulse` <- `Reset`. fit1: format **rgba32float**, `outputaspect resolution`; its
  `resolutionw/h = 1000` are saved but `outputresolution` is not in the changed list, so it should be Use Input (the family default,
  [OH:Resolution_TOP]); **if it comes up 1000x1000 after load, set `outputresolution` to `useinput`.**
- **Custom pars:** Reset (pulse), Drywet (default 0.5, saved 1), Scale (xy, default 1,1), Translate (xy, default 0,0),
  Brightness (default 1), Opacity (default 1, saved 0.99). All bound. **Cleanest control surface of the set.**
- **GLSL/Python:** none. **External:** none (stored input wire `fit1`). **Build:** 2023.11760.
- **Note:** fbStart is both the feedback seed and comp input 1, so the new frame is re-composited under the decayed trail each frame.

## 4. pixelSorting_MYLES (README: from Elekktronaut's Pixel Sorting)

- **Visual:** streaky vertical/horizontal smear of bright/dark areas. **Technique: it is not a true sort.** It is a difference +
  displace feedback loop that drags pixels along a direction.
- **Chain:** `in1 -> null2`; `null2 -> level1`; `null2 -> feedback1(top=add1)`;
  loop `feedback1 + level1 -> comp1(difference) -> displace1[in0 comp1, in1 level1 as displacement map] -> add1(+level1) -> feedback1`;
  output `add1 -> sub1(- level1) -> transform1(black bg, comp over) -> null1 -> switch1[0 = in1, 1 = null1] -> out1`.
- **Key pars:** level1 `brightness1` <- `Amount`; displace1 `displaceweightx/y` <- `Directionx/y`; switch1 `index` <- `Enable`;
  feedback1 `resetpulse` = `op('keyboardin1')['k1']` (dangling; bind `Reset`).
- **Custom pars:** Enable (toggle, default 0, saved on), Reset, Amount (default 0.1, saved 0.143), Direction (xy, default 0,0.01, saved 0,-0.02).
- **GLSL/Python:** none. **External:** stored input wire `videodevin1` (author's webcam, ignored). **Resolution:** follows input.
- **Rule for us:** displaces content: **not for names/words/logos** (whole-word rule).

## 5. dataMosh_MYLES (README: from Paketa12's Datamoshing, "any aspect ratio")

- **Visual:** datamosh-like smearing where the image appears to flow along drifting motion vectors, with optional mono/invert/contrast
  pre-process.
- **Chain (top level):** `in1 -> res1(rgba32float) -> select1 -> mono2(Monochrome) -> level1(invert/gamma 0.67/contrast) ->
  remap1[in0 level1 = image, in1 displace1 = UV map] -> null1 -> cross1[in0 level1 | in1 null1] -> out1`.
  UV-map loop: `ramp1(res1-sized, key table 0..1) -> flip1(bottomleft) ; reorder1(R = ramp, G = flip, rg32float) -> feedback1(top=displace1)`;
  `displace1[in0 feedback1, in1 base1/out1](green channel, weight 0.001, extend repeat) -> feedback1`.
  So the feedback holds a UV coordinate field that is nudged every frame by noise; the picture is re-mapped through it.
- **`base1` (inside):** `in2(feedback) -> mono1 -> res1..res9 (each Half, nearest) -> comp1(minimum of mono1,res2..res9)`;
  `noise1[in0 = reorder1, in1 = comp1] (rgb=subtract, rg32float) -> out1`. Noise TOP input 2 = per-pixel noise coordinates [OH:Noise_TOP],
  so the noise is evaluated at coordinates taken from a min-pooled copy of the field itself (self-referential flow).
  noise seed <- a Count CHOP of presses of the embedded Reset button (`op('null1')['v1']`), so every Reset reseeds.
- **Key pars:** noise1 `gain` <- Moshspread, `exp` <- Moshspeed, `amp` <- Moshgain, `offset` <- Moshdirection, `tz = absTime.seconds*0.2`;
  mono2 `mono` <- Monochrome; level1 `invert` <- Invert, `contrast` <- Contrast; cross `cross` <- Drywet.
- **Custom pars:** Reset, Drywet (default 0, **never saved non-zero: loads dry**), Monochrome, Invert, Contrast (1.25), Moshspread (0.65),
  Moshspeed (0.096), Moshgain (0.02), Moshdirection (0).
- **Python:** Palette `button` COMP (clone of `op.TDTox` `defaultCOMPs/button`; `externaltox` expression to
  `TDPackages/button/button.tox` with `enableexternaltox off`) with a panelexec (`parent().par.value0 = panelValue`) and parexec
  (`parent().panel.state = par.eval()`). Benign UI glue; both have `file` pars set to the unused relative `scripts/<name>.py`.
- **Resolution:** follows input (res1 only changes format). **Cost note:** 32-bit float field + 10 Resolution TOPs, 32F everywhere.
- Needs motion video as input to read as a datamosh; on still/generative content it is a warping filter.

## 6. circuitBending_MYLES (README: from Elekktronaut's Circuit Bending)

- **Visual:** analogue "circuit-bent" glitch: sliding bands, jitter, posterised smear, difference/exclude/negate/Z-film blends, optional
  random recolour via a 5-pixel noise lookup.
- **Chain, in order:** `in1 -> input(null) -> res1(rgba32float)`.
  Branches from res1: (a) `select1 -> cross1` (clean), (b) `level2(brightness 1.5) -> sharpen[Palette, Amount 0.883] -> comp1 input 1`,
  (c) `feedback1(top=comp1) -> level1(opacity 0.957) -> limit1(round, step 0.347) -> blur1(4) -> comp1 input 0`,
  (d) `feedback2(top=comp2)`.
  `comp1(operand index <- Blendmode via switch2 [constants 9, 13, 22, 28, 45]; menu Difference, Exclude, Inverse, Negate, Z Film; extend repeat; tx 4, ty 6 px)`.
  Band layer: `feedback2 -> noise1(period 1.8, harmon 6, 0.1) -> transform1(ty 6 px) -> comp2(difference with feedback2)`; comp2 -> displace1.
  Main path: `comp1 -> transform2(-14,-14 px, mirror) -> [noise2 -> noise3 (rgb=noise) -> displace2 (y 0.02) -> level3(0.92, contrast 2.5) -> slope1(strength 100)]` (the slope map);
  `displace1[transform2, comp2](0.01) -> displace3[displace1, slope1](Distort 0.47 default) -> displace4[displace3, noise5](x Jitter) ->
  transform3(ty <- Y-glitch noise, fractionaspect, repeat) -> lookup1[transform3, noise7](**bypassed unless Recolor**) -> level4 ->
  res2(Half) -> fit1(custom, size of op('input')) -> cross1[select1 | fit1] -> out1`.
  1x1 `noise4/noise6` TOPs become single values via `topto` CHOPs (`null1`, `null2`) that drive noise2/noise5 amplitude and transform3.ty. The `topto` read is a GPU to CPU readback of 1 pixel each frame.
- **Custom pars:** Reset, Drywet (default 0, **loads dry**), Distort (0.407), Jitter (0.01), Yglitch (toggle), Recolor (toggle),
  Colorseed (int 3297), Blendmode (menu of 5).
- **Python:** chopexec1: `onValueChange: op('lookup1').bypass = val` (Recolor toggle). Local, harmless. Two Reset expressions dangling
  (`keyboardin1`).
- **External:** embedded Palette `sharpen` with Jellybeans fallback image from `app.samplesFolder` (exists here, read-only). Stored input wire `dataMosh/out1`.
- **Cost/flash:** about 20 full-size TOPs with 7 Noise TOPs and difference blends at 32-bit float. Difference + exclude + noise jitter
  can strobe: **run through the flash governor (K_audio_reactive.md) before any LED use.**
- **Resolution:** follows input. `res2` Half then `fit1` restores the input size, which softens the final image.

## 7. abstractFluid_MYLES (README: Daniel Steenhoff's Abstract Fluid Simulation, modified to take video)

- **Visual:** the source is turned into glowing, oily, edge-lit fluid trails that swirl and slowly rotate/zoom; optional recolour through a
  ramp.
- **Chain:** `in1 -> null4 -> edge1 -> [feedback base] -> edge2 -> [feedback1 base] -> [feedbackEdge Palette] -> edge4 -> switch1 -> cross1 -> out1`.
  - `feedback` base: `in1 -> null1 -> comp1(over)[null1, level1]`, `feedback1(top=comp1) -> transform1(rotate +0.001, scale 1.001) -> level1(0.97) -> comp1`: trail with slow rotation. `feedback1` base is identical but rotate -0.001, scale 1.002 (counter-rotation = the "fluid" shear).
  - `feedbackEdge` (Palette 8.0.4): `in1 -> blur2(Blursource) -> level2(tint, Sourcegain) -> comp1(screen)`; the loop
    `feedback(top=null1=comp1) -> level1(black, gain, gamma 0.98, step threshold 0.9) -> transform1(Scale) -> blur1(Blurfeedback) -> hsvadj1(hue -2 per frame, sat) -> edge1 -> comp1`;
    `null1 -> dryWetMix(Drywet 0.25) -> out1`. Format rgba16fixed.
  - Recolour: `switch1[0 = edge4, 1 = lookup1[edge4, fit1]]` with `fit1` = `select3` of the **`Ramp` TOP par** resized to the input size
    (resx/resy from `info1`/`select2`/`null1`); `Recolor` toggles the switch. **The README's ramp is not in the tox; `Ramp` loads empty.**
  - `cross1[select1 = in1 | switch1]`, `cross` <- Drywet.
- **Custom pars:** Reset (expression `op('null2')['chan1']`, dangling), Drywet (0.85, saved 0.874), Edgestrength (1), Sourcegain (0.33),
  Feedbackgain (1.03), Recolor (toggle), Ramp (TOP reference).
  Palette-level pars (Scale 1.003, Hue Shift, Saturation, Edge Color, blur sizes) are inside `feedbackEdge`, not on the top page.
- **Python:** only the Palette `docsHelper` (stock). **External:** Palette fallback `Movie.2.mp4` (exists here). **Resolution:** follows input.
- **Why it is the best find:** three feedback stages with opposed rotations plus edge detection give a convincing fluid with only native
  TOPs and small kernels; the recolour via a Ramp makes it brand-able.

## 8. fallingLiquid_MYLES (README: from pppanik's Liquid Image Displacement)

- **Visual:** the picture melts and drips downward as if wet; liquid displacement driven by a vertically streaming noise.
- **Chain:** `in1 -> videoIn(null) -> fit1(custom size from in1 via info1; rgba32float) -> lumablur1[fit1, constant4]`.
  Flow field: `constant2 (resx x 10 px strip) + constant3 (resx x resy, alpha 0) -> comp1(over, nativeres, justify top) -> comp2(over)[noise1, comp1] -> fb_start -> feedback1(top=comp3)`;
  loop `feedback1 -> transform1(ty -0.001) -> displace1[transform1, noise2](y 0.001) -> level1(0.999) -> comp3(over)[level1, fb_start] -> feedback1`;
  `comp3 -> null2 -> noise3[null2, null2] (rgb=noise) -> slope1(strength 20) -> inside1[slope1, null2] -> constant4 (Constant TOP with Combine Input = inside)`;
  `lumablur1(whitewidth 33) -> displace2[lumablur1, inside1] (0.1, 0.1) -> out1(null) -> cross1[select3 = in1 | displace2] -> out2`.
  `noise1.tz` and `noise2.ty` <- `speed/out1['speed']` (a Speed CHOP integrating a constant 0.145, sub-COMP `speed` holds a custom `Speed` par).
- **Custom pars (top):** Reset (pulse; its expression `op('select1')['ch1n76']` points at a channel that does not exist), Drywet (default 0, **loads dry**).
  `Speed` (0.145) lives on the inner `speed` base, not on the top page.
- **Python/GLSL:** none. **External:** none (stored input wire `ndiin1`).
- **Resolution:** all generators sized from the input (`op('constant1')['resx']`); noise is 256 wide by default but resized.
- **LED note:** flow is strictly downward, which suits the tall vertical 1080x1920 faces; background media only (displacement).

## 9. randRectComp_MYLES (README: "masks it into two rectangles created randomly")

- **Visual:** two random rectangles appear over (or reveal) the input, repositioned on each "Randomize" pulse.
- **Chain:** `in1 -> null2` and `in1 -> rectangle1/2 (combineinput res)`; `rectangle1 + rectangle2 -> comp1(add)`;
  `comp2[null2, comp1] (default operand, Over) -> out1`. Randomness: `trigger1 (pulse <- Randomize) -> rename1(v1) -> count1, count2 -> null1/null5 -> pattern1..4 (random, seed = count/1000 or /2000) -> lookup1..4 -> math1..4 (gain 0.75/0.5) -> math5..8 (re-range) -> null3..11 -> rectangle sizex/sizey/centerx/centery`.
  `constant3 (Enable) -> math9 (inverted) -> null12 -> chopexec1: op('comp2').bypass = val` (Enable off bypasses comp2, giving the clean video).
- **Custom pars:** Enable (toggle, default 0, saved on), Randomize (pulse).
- **Python:** chopexec1 only (sets `comp2.bypass`). **Rectangle:** red border colour, width at default; fill colour is not in the changed
  list so is the default; because comp2 is a plain Over, whether the rectangles act as a mask or an overlay cannot be decided from text:
  **test visually** (open question).
- **Open flag:** `trigger1` is saved with par name `triggerpulse`; the 31550 Trigger CHOP's pulse par is `trigger` [DUMP]. TD usually maps
  legacy names, so verify Randomize still fires after load.
- **GLSL/external:** none. **Resolution:** follows input.

## 10. randomNumber_MYLES and randomVideoFile_MYLES (helpers)

**randomNumber** (CHOP-in, CHOP-out): `in1 | lfo1(pulse, Frequency)` -> `switch1(index <- Internalpulse)` -> `count1` (counts the pulses) ->
`lookup1[count1, pattern1(random, seed <- Seed)]` (indices 0..1000) -> `math1(range <- Range)` -> `numberOut`, plus `pulseOut`.
A deterministic seeded random-number stream stepped on each pulse. Pars: Seed (int, default 1, saved 32), Internalpulse (toggle, default 1),
Frequency (default 1, saved 2), Range (xy, default 0,1). No code, no files.

**randomVideoFile** (CHOP in = pulse): `folder1 (Folder DAT, async) -> select1 (rows from 1) -> sort1 (random, seed <- embedded randomNumber)
-> select2 (cols from 1) -> null2 -> moviefilein1.file = op('null2')[0,0] -> out1`. Embeds a copy of `randomNumber`. Pars: Folderdirectory,
Internalpulse (default 0, saved on), Frequency (2.52), Seed (32).
- **External/audit:** `folder1.rootfolder` holds the author's path **`/Users/aaronpereira/Documents/Installation/Adidas x Magnanimous/OUTPUT`**
  (bound to the `Folderdirectory` par). It does not exist here; set a folder first. The Folder DAT only lists names and Movie File In
  opens whatever file it picks, so it is "reads files from the folder you point it at". `folder1_callbacks` is the unmodified template
  (`onGetInclude` returns True). Leaks the author's username and a client/project name (do not copy them into our docs).
- **Open:** `select2` starts at column 1; which Folder DAT column is then `[0,0]` (path vs base name) depends on default column order;
  if a bare name results, the movie will not open. Test.
- Movie switching on a live feed hitches; Arena is the clip player, so low value for us.

## 11. reactionDiffusion_MYLES (README: Ben Heim's Reaction Diffusion)

- **Visual:** self-organising organic cell/coral patterns that grow and drift, from noise (no input needed).
- **Chain:** `noise1 (Resolution par; seed 2021, tz = absTime.seconds*0.5) -> feedback1(top=comp1)`;
  `feedback1 -> blur1(Blur1, preshrink Shrink1) -> blur2(Blur2, preshrink Shrink2)`; `sub1 = blur1 - blur2` (a difference of Gaussians, the
  activator/inhibitor core) `-> sharpen[Palette; Amount <- Sharpen] -> feedbackEdge[Palette; Scale <- Speed, Feedbackgain, Drywet <- Feedbackedge] -> transform1(rotate 0.001) -> level1(brightness 4, gamma 2.2) -> comp1(over)[level1, noise1] -> feedback1 / out1`.
- **Custom pars:** Resolution (xy int, default 1920,1080), Reset, Blur1 (41), Shrink1 (1), Blur2 (72), Shrink2 (1), Sharpen (1), Feedbackedge (1),
  Speed (1.02), Feedbackgain (1.101). Reset expression dangling (`keyboardin1`) on feedback1 and feedbackEdge.
- **Python:** `chopexec1` is the empty template (no CHOP set); plus two stock Palette `docsHelper` sets. **External:** Palette fallback `Jellybeans.1.jpg` (exists here).
- **Resolution:** generator at its own `Resolution` par (1920x1080 default): **change to 1080x1920.** Big blur kernels (41, 72) at that size are
  the cost; consider Resolution at half and upscale. No measurement was made (no performance claim).
- **Multi-pass note:** no GLSL, but at least 12 TOP passes in one feedback loop (blur x2, sub, convolve, 8+ inside feedbackEdge). Apply T-46 caution.
- Fits `O_generative_simulations.md` (RD there is planned as a GLSL/compute sim; this is the cheaper native alternative).

## 12. Audit

Build stamp from `.build` (all `version 099`, `osname macOS`): saved 2024-04-13 to 2024-06-13, macOS 14.4.1 / 14.5.

| tox | runs code on load? | file / network access | external files | Mac / 31550 issues | safe to load |
|---|---|---|---|---|---|
| simpleFeedback | no | none | none | stored input wire `particlesGpu/out1` (ignored) | yes |
| feedback | no | none | none | fit1 should be Use Input (else 1000x1000); stored wire `fit1`; 32F | yes |
| pixelSorting | no | none | none | Reset expr `keyboardin1` dangling; wire `videodevin1`; displaces content | yes |
| dataMosh | no (Palette button panelexec/parexec react to clicks only) | none | none (button.tox ext. path, `enableexternaltox off`) | needs `op.TDTox`; 32F + 10 Resolution TOPs; loads dry (Drywet 0) | yes |
| circuitBending | stock Palette DocsHelper extension on load; chopexec sets local bypass | none | Jellybeans.jpg (app samples, exists) | Reset expr dangling; 32F, 20+ passes; flash risk; loads dry | yes |
| abstractFluid | stock Palette DocsHelper extension on load | none | Movie.2.mp4 (app samples, exists); `Ramp` TOP not included | Reset expr `null2` dangling; rgba16fixed format unverified here | yes |
| fallingLiquid | no | none | none | Reset expr refers to a channel that does not exist; loads dry; wire `ndiin1` | yes |
| randRectComp | chopexec sets local bypass only | none | none | `triggerpulse` vs 31550 `trigger` (check); Over-order unclear | yes |
| randomNumber | no | none | none | none found | yes |
| randomVideoFile | no (Folder DAT scans on load, async) | **lists a folder and opens the file it picks** (path is set by the user) | **author path `/Users/aaronpereira/...Adidas x Magnanimous/OUTPUT` does not exist** | `select2` column pick unverified; hitch on switching | yes (set the folder first) |
| reactionDiffusion | stock Palette DocsHelper (x2, in sharpen and feedbackEdge) | none | Jellybeans.jpg (exists) | Resolution default 1920x1080; Reset expr dangling; long feedback chain (T-46) | yes |

Checked and found absent in all 11: `import`, `os.`, `subprocess`, `socket`, `urllib`, `webbrowser`, `exec(`, `eval(` as code, `open(`, GLSL
DATs, Script DATs, Web/Network/Serial/OSC/MIDI DATs or CHOPs, WebSocket, external `.tox` loads (only the one Palette `button` path with the switch off),
`Execute DAT` start/create/onProjectPreSave hooks. Only one URL appears: `https://www.derivative.ca` (Palette DocsHelper default, used only when
you press its Help pulse).
Safe means safe by static reading; it is not a verified-run claim.

## 13. Adapt ranking for LED concert visuals (1080x1920, brand, no words distorted)

General changes for any of them: set the root to 1080x1920 explicitly (or let it follow a Select of our look); use rgba16float instead of
32-bit float; default `Drywet` to 1 (several load dry); remove `keyboardin1`/`null2`/`select1` expressions and keep only the
`parent().par.Reset` bind; delete the unused `docsHelper` containers; arrange the network (td_layout); put controls on a clean custom
page; hook the strongest 2-3 pars to audio features (K_audio_reactive.md); put the flash governor on anything with difference/noise
flicker; leave the tox files out of PF26 content and rebuild (licence caveat above).

| # | tox | worth adapting? | what to change |
|---|---|---|---|
| 1 | abstractFluid | **Yes, top pick.** Fluid/oil trails read as expensive on a tall wall and are cheap-ish (small kernels, native TOPs). | Feed a generative colour field (noise/particles/our looks), not live video. Supply a PRISM-palette Ramp TOP (full-colour brand gradient) and make Recolor default on. Expose Scale, Hue Shift, Edge Strength, Feedback Gain on the top page. Audio: Feedback Gain (kick) and Hue Shift (slow). Watch trail saturation (Feedback Gain over about 1.07 blows out). |
| 2 | reactionDiffusion | **Yes.** A standalone generative background that needs no input and loops forever. | Resolution 1080x1920 (or half then upscale); recolour the black/white result with a Lookup on the brand ramp; add a seed-based Reset and a periodic gentle re-seed to avoid a frozen state; test T-46 (torn frames) with Movie File Out; bind Speed/Blur1 to a slow LFO. Compare with O_generative_simulations.md before building. |
| 3 | feedback | **Yes, as the template for the pattern**, not the look. | Keep its control surface and bind scheme as the house style; add rotate and hue shift; remove 1000x1000 doubt; rgba16float; default Drywet 1. |
| 4 | fallingLiquid | **Maybe**, for atmospheric melt on vertical walls, backgrounds only. | Apply to imagery with no names/logos/text; expose Speed on the top page; default Drywet 1; reduce displace2 weight (0.1) for readability; cap the 33 px luma blur for cost. |
| 5 | circuitBending | **Maybe** as a short stinger/transition. | Wrap in the flash governor and a hard Drywet envelope (set the max flashes per second per K_audio_reactive.md); trim noise/blend count (7 noises); not on text. |
| 6 | dataMosh | **Low-medium.** Only meaningful on motion video; effect is a transition glitch. | Use on the artist clip library at transitions; automate Reset on cut; keep the float field at 16F; default Drywet 1. |
| 7 | pixelSorting | **Low.** Cheap smear, not a real sort; for a real sort use the GLSL compute route in O/V docs. | Only as a cheap directional smear stinger; Direction to a slow LFO. |
| 8 | randRectComp | **Low.** The pattern (seeded random per pulse -> rectangles) is useful for face-by-face reveals across the 9 faces. | Rebuild with 9 face rectangles from the R02 map instead of two random ones. |
| 9 | randomVideoFile | **Low** (Arena plays clips). | If kept, replace the folder, use two Movie File In decks with a crossfade to avoid hitching. |
| 10 | randomNumber | **Low**, trivial helper. | Python/CHOP equivalent already exists in our show framework; do not import. |
| 11 | simpleFeedback | **Skip.** | feedback covers it. |

## 14. Open questions

1. Why 12? The repo has 11 `.tox`; confirm no twelfth was expected (README is silent).
2. Is `Resolution TOP` `fit1` in `feedback_MYLES` really Use Input (the changed list omits `outputresolution`)? Settle after one safe load.
3. `op('keyboardin1')` and `op('null2')`: does TD search up the hierarchy for a bare op name? If a same-named op exists in our rig these
   resets would bind to it (not an issue in a clean scratch COMP, but name collisions with `null2` are possible).
4. Do loaded input connections auto-wire to same-named ops (`fit1`, `out1`, `dataMosh/out1`, `pulse1`) in our network? Verify with `td_info`.
5. Composite TOP input order for Over (randRectComp comp2 and the feedback comps): rectangle as mask or overlay? Test visually.
6. Blendmode constants 9, 13, 22, 28, 45 in circuitBending: which Composite TOP operand each is in 31550 (menu order could differ from 2023.11600).
7. `triggerpulse` (file) versus `trigger` (31550) on the Trigger CHOP: is the Randomize wire kept?
8. Folder DAT default column order in 31550 (what `select2` column 1 is).
9. T-46 on native TOP feedback loops: measure torn frames for reactionDiffusion and abstractFluid on this Mac before any live use.
10. The README says to host each tox in an Engine COMP to parallelise. Does the Engine COMP work here (Rosetta, Vulkan, TouchEngine helper
    present in the bundle) and with Syphon? Not tested; no recommendation.
11. Licences of the original tutorial networks (not stated by the author): a shared decision for the licence ledger (L_shader_sources_licences.md).

## 15. Evidence files (scratch, deleted)

Each tox expanded to `<scratch>/toxes/<name>/<name>.tox.dir/` (one text file per op: `.n` type/wiring/flags, `.parm` non-default pars, `.text` DAT
text, `.cparm` custom pars, `.build`). Expanded size ranged from 16 files (simpleFeedback) to 165 files (circuitBending; reactionDiffusion 157; both include embedded Palette parts).
