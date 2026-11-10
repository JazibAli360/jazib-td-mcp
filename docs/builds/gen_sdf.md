# gen_sdf: GEN_sdf rack + 10 raymarch / fractal / sky modules (live in main, 26-27 Oct 2026, TD 2025.31550)

`/project1/lab/GEN_sdf`. FX0 rows 41 (SDF raymarch toolkit) + 67 (fractal explorer), FX0 "GEN_sdf" line; FX5 G13
(sdfscene with preset scenes) + G14 (Mandelbulb / Mandelbox / Julia / 2D with deep zoom). Research and sources:
`docs/research/BS_sdf_raymarch_fractals.md`.

**Status: live on 2025.31550 (built in b5, in the main .toe `JazibTD_home.388.toe`): 3 modules, 21 presets verified,
see "Verified live" (+ "Perf pass" below it). 19 offline tests; every shader compiles with glslc.**

## Design (lean: GEN_pattern's rack reused, not copied)
`builders/gen_sdf.py` execs `builders/gen_pattern.py` (read-only) and reuses its rack: `slots` table (`name module
enabled order mix`), per slot module COMP -> `_mix` (Cross) -> `_slot` (Switch), `drive` CHOP (beats / bpm / level),
Panic, background (Input auto / black / live / test), `add` / `remove` / `rewire` / `preset` / `freeze` /
`unfreeze`. What differs is the module network, because a raymarch needs its own resolution and float output:

`clock -> clock_int` (module time) ; `[ref ->] rm` (compute GLSL at `Quality` x input res, **rgba32float, premultiplied
rgb + alpha**) ; `in1 + rm -> fx` (shared composite at input res: bilinear upscale + Blend + Amount; **Amount 0 = exact
texelFetch passthrough**) `-> out1`. Two GLSL inputs at most (T-88).

Two kinds of module (shared GLSL lives in gen_sdf.py because 2+ modules use it today):
- **ray** (`scene`, `fractal`) write `void setup()`, `float map(vec3 p)`, `float mapk(vec3 p)` (palette coordinate at
  the hit). The shared core does: camera paths (orbit / fly / wander, FOV, roll + roll speed, sway, beat yaw jumps,
  beat / audio dolly, object spin), sphere tracing (`Overrelax` > 1 = over-relaxed, Keinert et al. 2014, with the
  safe fallback; 1 = classic, the default) with a **pixel-sized hit threshold** (`Epsilon` px x pixel angle x
  t), tetrahedral normals, IQ soft shadows, 0-8 tap AO, 5 materials (matte, glossy, chrome = sky reflection, neon =
  rim + emissive, toon = 3 bands + outline), exponential fog to transparent (Bgcolor behind in Replace), near-miss glow
  (+ beat pulse), views (shaded / data / normals / step-count heat).
- **flat** (`fractal2d`) writes `vec4 render2d(vec2 P)`.

**Loop caps (T-124):** every loop runs to a compile-time cap: march `MAXSTEPS` 512, shadow 64, AO 8, fractal 32,
2D 8192 (the test `test_loops_bounded` refuses a uniform loop bound). Users raise `Steps` / `Iterations` up to the caps;
`Quality` (0.1-2, 2 = 4x SSAA) scales the cost; `Still` (Render page) locks `rm` so a finished frame costs nothing
(deep zoom stills). No built-in look limits (no flash / rate caps).

Drive (module page, all modules, GEN_pattern's): Speed, Phase, Audiospeed, Audiogain, Beatevery, Beatgain, Beatdecay,
Seed. Shader globals `T STEP AGE ENV LEVEL SEED RES`. Colour page: Palette (duo / solid / rainbow / fire / ice / gold /
neon / sunset), Spread, Offset, Huecycle, Colour A/B, **Bgcolor (= fog colour)**, Blend (Replace, Over the input, Add,
Screen, Multiply, Difference, Alpha out premultiplied).

Files: `builders/gen_sdf.py` (rack glue, shared GLSL, specs, check helpers), `builders/gen_sdf_{scene,fractal,
fractal2d}.py` (data + GLSL; fractal2d also holds the reference-orbit Python `REF_PY` that both the Script TOP and the
mirror run), `builders/gen_sdf_logic.py` (numpy float32 mirror of every shader line: `expect_rm`, `compare`,
`compose_px`, `out_stats`, `render_img`), `test/test_gen_sdf.py`. Run:
`python3 -I -m unittest discover -s test -p 'test_gen_sdf.py'` (17 tests, ~3 s).

## Modules
| Module | What | Presets | Audio / beat |
|---|---|---|---|
| scene | 8 scenes in one shader: box tunnel, gyroid cave (gyroid sheet with a fly tunnel along z), Menger sponge, Apollonian foam, blob orbit (<= 16 smooth-min spheres on Lissajous paths), neon lattice, city blocks (hashed heights, cell-bounded steps), gyroscope rings (<= 6 rotating tori). Modifiers: Size, Repeat, Twist, Fold (kaleido around y). **Morph** Scenea -> Sceneb (Morph + Morphswing ping-pong at Morphrate + Beatmorph). | 1 box tunnel, 2 gyroid cave, 3 menger sponge, 4 apollonian glow, 5 blob orbit, 6 neon lattice, 7 city beat, 8 gyroscope, 9 morph sponge-blobs | level + pulse thicken walls / rods / rings, grow blobs, raise city blocks; Beatmorph |
| fractal | Mandelbulb (power n, Powerswing / Powerspeed / Beatpower, Bailout), Mandelbox (Boxscale, Foldlimit, Min / Fixed radius), quaternion Julia (4D c), KIFS Menger fold (scale, offset, rotate + speed). **Juliamix** morphs Mandel -> Julia for bulb + box; Julia c orbits. Orbit-trap colour. Whole powers (Power 2-16 with no swing) run trig-free (complex powers of the two angles; same maths). Defaults: Quality 0.35, Steps 128, Stepscale 0.8, shadows off, AO 3. | 1 mandelbulb, 2 bulb breathe, 3 julia bulb, 4 mandelbox, 5 quaternion julia, 6 kifs temple; SX-23 glow presets (lane C2, 27 Oct, existing types, near-miss glow + fog carry the look): 7 kifs glow orbit, 8 box cathedral (Boxscale 2, wander), 9 julia glow (beat glow), 10 power coils (power 3 Julia, swing) | level -> power; beat pulse -> power (Beatpower) |
| fractal2d | Mandelbrot, Julia, Burning Ship, Tricorn, Multibrot z^n (power swing). Colouring: smooth iteration (log), trap point / line / circle, edge (distance estimate, px width). Interior black / trap. Dive (Zoomspeed octaves/s), Beatzoom, Rotate + speed. **Precision perturb** (Mandelbrot / Julia): `ref` Script TOP computes the reference orbit in Python float64 (Decimal when `Deepx` / `Deepy` hold digit strings), stored as hi + lo float32 pairs; float32 deltas + rebasing in the shader. | 1 mandelbrot, 2 seahorse dive (perturb, 0.5 oct/s), 3 julia orbit (edges), 4 burning ship, 5 multibrot traps, 6 deep 1e10 still (perturb; use Still) | level + pulse -> zoom octaves |

| aurora (lane C, 27 Oct; FX7a SX-13 + FX7c 7C-13; flat) | Aurora curtains, clean-room (no CC BY-NC-SA code): a fixed camera (Tilt, Yaw + Yawspeed, Fov) looks up through Layers (cap 64) emission layers at Height + i x Spacing; each ray meets layer i at t = h / rd.y (cap 60) and reads a curtain field there (4 octaves of a domain-warped triangle-wave pattern, Warp, Sharp = thinner folds, Scale, Flow motion, Driftx / Driftz); colour = the palette at the layer's height (duo green -> magenta by default), exp height Fade + distance haze; horizon falloff, hashed twinkling stars (Stars, Starscale, Twinkle), optional rippled water mirror (Reflect, Ripple). Default Quality 0.5. Data view = (layer mean, rd.y, g, 1). | 1 green curtains, 2 violet storm, 3 polar mirror, 4 beat veil, 5 slow drift | Beatglow (beat pulse) and Audioglow (level) -> intensity |

| sky (lane C, 27 Oct; FX7a SX-18; flat) | Single-scatter sky, port of wwwtyro/glsl-atmosphere (Unlicense) in km: Rayleigh + Mie densities from scale heights, Steps (cap 32) x Lightsteps (cap 16), Rayleigh + Mie phase (Mieg); the eye starts inside the atmosphere (integration from 0, ground roots behind the eye ignored: the original integrates behind the camera). Sun from Daytime (0..1 = a day; Sunspeed auto cycle) or Sunelev / Sunazim; sun disk; ground = dimmed aerial haze over Bgcolor; tone map 1 - exp(-Exposure c). Fixed camera Tilt / Yaw / Fov. | 1 golden hour, 2 noon, 3 sunset haze, 4 twilight, 5 day cycle | - (drive it from the timeline / MIDI) |

| planet (lane C, 27 Oct; FX7b TC-34; flat) | Analytic ringed gas giant, clean-room from Yaado Lab's description: closed-form ray hits on a flattened sphere (Flatten, Axistilt), the ring plane (Ringin .. Ringout, Ringbands, a gap) and up to 3 moons; closed-form shadows (rings on the planet, planet on the rings). Bands = palette at sin(lat x Bands + turbulence), Turb / Turbspeed, Shear (differential rotation), Spin; one oval storm with swirl rings; soft terminator + atmosphere rim (Colour A); stars. Orbit camera (Camdist, Camyaw, Campitch, Orbitspeed, Fov, Beatzoom). Default Quality 1.0 (cheap, crisp limb). Data view = (t planet, t ring, ring density, alpha). | 1 ringed giant, 2 close pass, 3 edge-on rings, 4 ice giant, 5 beat orbit | Beatzoom (dolly on the beat pulse) |

**scene + `stairs` (lane C, 27 Oct; FX7b TC-35 dreamcore):** scene 8 = 24 floating steps on a helix (12 per turn):
the step index comes from the angle and the height, so only 3 boxes are tested per sample; each step bobs and tilts
on its own phase; a door frame with a thin light panel at the top; a rolling cloud sea below. Preset 10 `dreamcore`
(pastel duo palette, pale lilac fog, glow). Clean-room from Yaado Lab's description (30 Sep 2026).

Float mode is good to zoom ~1e4 (float32 centre); perturb mode to ~1e30 (float32 delta range); past ~1e13 the centre
must come as `Deepx` / `Deepy` strings (Decimal reference, CPU cost only when centre / iterations / Julia c change; an
orbiting Julia c recomputes each frame).

## LIVE CHECKS (build TD b5, then main)
Rules: `python3 tools/lane.py add /project1/lab/GEN_sdf "<lane>"` first, `remove` at the end; build TD only
(`python3 tools/scratch_td.py run --name b5 "<python>"`); one structural change per call; state / pixel reads in a
separate exec >= 3 frames after a change (T-74 / T-116 (4)); T-124: start at low Quality / Steps and raise only after
the first frames come back clean; never change cookRate.

Exec preamble: `ns = dict(globals()); exec(open('<repo>/builders/gen_sdf.py').read(), ns)`; `C = '/project1/lab/GEN_sdf'`.

**Step 0 rack:** `ns['build']('/project1/lab')` -> rack + `scene1`. Expect errors clean on C and C/scene1 (watch for a
GLSL symbol clash with TD's compute header: `TAU PI T STEP AGE ENV LEVEL SEED RES h2 rot2 smin sdBox tri pal palk
SPIN sdf sdfk map mapk setup camera normal shadow ambocc sky shade`), `rm` 540 x 960 rgba32float, `fx` 1080 x 1920,
`slots` 1 row, out1 not black. Then `add` fractal and fractal2d (each: errors clean, numBlocks = spec: scene 22,
fractal 24, fractal2d 14; fx 2).

**Per module (A-E):**
- **A Parity, data view:** `preset(I, k)`, `I.par.View = 'data'`, `freeze(I)` (t 1 s, beats 0); next exec
  `check(I)`. Ray: **hit_agree >= 0.95, t_within (2 % rel) >= 0.9** on pixels both call hits. Flat: **esc_agree >=
  0.95, mu_within_0.5 >= 0.9** (float32 chaos at the set boundary and in deep presets lowers it; the offline float32 vs
  Decimal number for deep 1e10 is 0.85 within 0.05).
- **B Parity, shaded:** View shaded, freeze, `check(I)` -> **within_tol (4/255) >= 0.85, median <= 0.01** (silhouette
  and chaotic pixels flip; that is the expected miss). Then `check_fx(I)` (composite vs live rm + in1) -> **max <=
  2/255** (exact bilinear + blend path).
- **C Stats (doc table):** `stats(I)` with the rack Input black, Blend replace: mean rgb within +-0.03 and lit within
  +-0.03 of the table (fractals and the deep presets: +-0.06).
- **D Passthrough + drive:** Amount 0 -> out1 vs in1 max diff **0**; slot enabled 0 / Panic -> 0 vs `img_src`.
  Unfreeze; Beatevery 1 + Beatgain 1 at Bpm 120: `uDrv.y` steps +2 per s (pane on the rack, T-124 (2)).
- **E Cost + fps + capture:** pane off the rack; median GPU ms of `rm` + `fx` over ~120 pulled frames (T-102 method)
  at the preset's own Quality, 1080 x 1920 output; real fps (Execute DAT frame counter over 5 s, T-124 (4)) with only
  GEN_sdf un-parked. One `td_screenshot` of the instance out1. Aim **<= 3 ms** at the default quality; report the real
  number and the Quality / Steps that meet it when a preset is over.

Over budget: lower `Quality` first (fractals 0.25-0.35), then `Steps`, `Shadowsteps`, `Aosteps`; fractal2d:
`Iterations`.

### Expected numbers (mirror; frozen t = 1 s, beats 0, no audio, Input black, Blend replace, out 1080 x 1920)
`gen_sdf_logic.out_stats` at `gen_pattern_logic.sample_points(1080, 1920)` (seed 7); lit = luma > 0.5. rm size = the
preset's Quality x 1080 x 1920. Regenerate after any change (the scratch script pattern: `module_pars` -> `uniforms`
for rm (W, H = rm size) and `FX_UNIFORMS` -> `out_stats`).

| Module | Preset | rm | Mean rgb | Lit |
|---|---|---|---|---|
| scene | 1 box tunnel | 540x960 | 0.087 0.067 0.128 | 0.000 |
| scene | 2 gyroid cave | 540x960 | 0.144 0.086 0.069 | 0.005 |
| scene | 3 menger sponge | 540x960 | 0.199 0.089 0.010 | 0.001 |
| scene | 4 apollonian glow | 540x960 | 0.455 0.232 0.304 | 0.056 |
| scene | 5 blob orbit | 540x960 | 0.136 0.141 0.153 | 0.144 |
| scene | 6 neon lattice | 540x960 | 0.182 0.175 0.230 | 0.009 |
| scene | 7 city beat | 540x960 | 0.212 0.206 0.229 | 0.072 |
| scene | 8 gyroscope | 540x960 | 0.037 0.024 0.010 | 0.011 |
| scene | 9 morph sponge-blobs | 540x960 | 0.069 0.022 0.022 | 0.007 |
| fractal | 1 mandelbulb | 378x672 | 0.206 0.146 0.078 | 0.044 |
| fractal | 2 bulb breathe | 378x672 | 0.069 0.180 0.142 | 0.018 |
| fractal | 3 julia bulb | 378x672 | 0.208 0.106 0.100 | 0.079 |
| fractal | 4 mandelbox | 378x672 | 0.111 0.061 0.078 | 0.012 |
| fractal | 5 quaternion julia | 378x672 | 0.399 0.222 0.176 | 0.204 |
| fractal | 6 kifs temple | 378x672 | 0.135 0.195 0.346 | 0.100 |
| fractal2d | 1 mandelbrot | 810x1440 | 0.277 0.656 0.264 | 0.706 |
| fractal2d | 2 seahorse dive | 378x672 | 0.584 0.303 0.249 | 0.370 |
| fractal2d | 3 julia orbit | 810x1440 | 0.046 0.061 0.049 | 0.049 |
| fractal2d | 4 burning ship | 810x1440 | 0.228 0.156 0.044 | 0.099 |
| fractal2d | 5 multibrot traps | 810x1440 | 0.827 0.423 0.362 | 0.522 |
| fractal2d | 6 deep 1e10 still | 540x960 | 0.430 0.750 0.925 | 0.994 |

## Verified live (26 Oct, 2025.31550, built in build TD b5, brought home into main)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
b5 shared the Mac with 5 other busy TDs (main, scratch, b2-b4, each 60-90 % CPU), so GPU times are noisy; numbers
below are medians of ~90 forced out1 pulls (p10 / median / p90 in the run log), pane off the COMP.
- **Rack:** build clean (errors 0, no GLSL symbol clash with TD's compute header), rm 540x960 rgba32float, fx
  1080x1920, `add` fractal / fractal2d: 7 wires each, numBlocks 22 / 24 / 14 (fractal2d gained `uM6`), layout ok
  (1093 ops with 3 zkit panels).
- **Parity, all 21 presets:** data view hit / escape agreement 1.0 (seahorse 0.995), t identical (rel median 0.0);
  fractal2d mu within 0.5: 1.0 for float presets, burning ship 0.965, deep 1e10 0.94 (float32 chaos, mirror and GPU
  share the reference). Shaded within 4/255: 1.0 on 18 presets, 0.965-0.995 on burning ship / seahorse / deep.
  `check_fx` (composite vs live rm + in1): max 0.0019-0.0043 every preset. **`stats` = the table above for every
  preset** (all within 0.001).
- **Deep zoom on the GPU vs exact maths:** zoom 1e14 with `Deepx` / `Deepy` 33-digit strings (Decimal reference, 4001
  entries, 11.9 ms Python on change): smooth mu equal to an exact Decimal iteration (prec 45) on 22 / 24 random rm
  texels (the other 2 within 0.12). Live bug fixed: the zoom scale 3/Zoom read 0 because TD snaps par values below
  1e-5 to 0 (T-136); now passed as log2.
- **Passthrough:** Amount 0 -> out1 = in1 exactly (max 0, all 3 modules, test clip in); slots enabled 0 -> rack out1 =
  img_src (0); Panic -> 0. **Drive:** Bpm 120 Beatevery 1: step +3 and T +1.37 in 1.37 s.
- **Still:** toggle locks `rm` (Parameter Execute -> `rm.lock`): deep 1e10 at 540x960 costs 43-62 ms GPU per frame
  unlocked, ~0.3 ms (fx only) with Still on, picture kept (stats unchanged).
- **fps** (real frames, Execute DAT counter, out1 force-pulled each frame, b5 under the load above): GEN_sdf parked
  59.6; scene sponge 59.3, apollonian 56.7; mandelbulb 59.7, bulb breathe 58.7; seahorse dive 58.5, multibrot 59.9;
  all three slots chained (sponge -> bulb -> mandelbrot) 54.3.

| Module | Preset | rm GPU median ms (p10) | fx ms | Note |
|---|---|---|---|---|
| scene | 1 box tunnel | 1.9 (0.2) | 0.45 | |
| scene | 2 gyroid cave | 3.3 (0.4) | 0.66 | |
| scene | 3 menger sponge | 2.0-2.6 (0.4) | 0.17-0.66 | 2.0 at the quieter start of the run |
| scene | 4 apollonian glow | 5.6 before Detail 3 / Epsilon 1; noisy 7-12 after | 0.8 | over: Quality 0.35 or Steps 64 |
| scene | 5 blob orbit | 1.9-4.5 | 0.2-0.4 | |
| scene | 6 neon lattice | 2.3-4.4 | 0.3 | |
| scene | 7 city beat | 3.6-4.5 | 0.2-0.6 | over: Shadowsteps 8 or Quality 0.4 |
| scene | 8 gyroscope | 2.2-3.1 | 0.4-0.6 | |
| scene | 9 morph sponge-blobs | 3.0-6.0 | 0.3-0.7 | two scenes per step while morphing |
| fractal | 1 mandelbulb | 3.8 (2.1); 5.8 before Epsilon 1 | 0.6 | Quality 0.3 for <= 3 |
| fractal | 2 bulb breathe | 5.2 (2.5) | 0.8 | over: Quality 0.3 |
| fractal | 3 julia bulb | 4.9 (0.1) | 0.3 | |
| fractal | 4 mandelbox | 2.6 (0.05) | 0.1 | |
| fractal | 5 quaternion julia | 1.1 | 0.2 | |
| fractal | 6 kifs temple | 0.75 | 0.3 | |
| fractal2d | 1 mandelbrot | 2.3-4.1 | 0.3 | |
| fractal2d | 2 seahorse dive | 3.4 (0.6); 87 at Quality 0.75 / 1024 it | 0.4 | interior pixels run all iterations in perturb mode |
| fractal2d | 3 julia orbit | 2.7-3.3 | 0.3 | |
| fractal2d | 4 burning ship | 1.0-2.4 | 0.2-0.6 | |
| fractal2d | 5 multibrot traps | 5.4 (1.5); 18 at 256 it before the cycle check | 0.7 | |
| fractal2d | 6 deep 1e10 still | 43-62 live, **~0 with Still** | 0.2 | a deep zoom is a still or a heavy mode |

Live tuning from these numbers: fractal default Epsilon 1.0 px (mandelbulb 5.8 -> ~2.9-3.8 ms); apollonian Detail 3 +
Epsilon 1; city Shadowsteps 16; multibrot Iterations 96 + Brent cycle check (float mode, `Cyclecheck`, interior
orbits stop early; offline test: escapes and mu unchanged); seahorse dive Quality 0.35 / 600 iterations; deep 1e10
Quality 0.5 + the `Still` toggle. The 3 ms aim is met at the default quality by the simpler scenes, mandelbox,
quaternion Julia, KIFS and the float 2D presets; the heavier presets are listed with the knob that brings them under.
Captures (b5 out1, 1080x1920): `output/gen_sdf_scene1_neon_lattice.png`, `output/gen_sdf_fractal1_mandelbulb.png`,
`output/gen_sdf_fractal2d1_julia_orbit.png`.
- **Brought home:** `node tools/bring_home.mjs --comp /project1/lab/GEN_sdf --from b5`: main ops 1093 = b5, errors
  0, parked, **main saved `JazibTD_home.388.toe`** (b5 `Build5.23.toe`). Rest state: scene1 enabled (preset 3), fractal1
  / fractal2d1 enabled 0, Still off, Input auto, Bpm 120. (The tool refuses a COMP registered in active_lanes.json, even
  the lane's own: remove the registration first, then bring home.)

## Perf pass (26 Oct, 2025.31550, b5 -> main; perf lane)
Method: **paired A/B in the same frames** (the old shader text in a copy `rm_ab` of `rm`, same uniform expressions,
both force-cooked every frame in alternating order, GPU ms per op, 100-200 frames, one sample per frame; ratio
old / new median). Under 6 busy TDs single-op medians moved 2x between runs; the paired ratio is stable (A/A check
on the same text: 0.98-1.01). Changes:
- **fractal Mandelbulb, whole powers trig-free:** Power 8 (no swing / beat) iterates `(cos th + i sin th)^n`,
  `(cos ph + i sin ph)^n`, `r^n` by binary powers (no acos / atan / pow / sin / cos); `r^(P-1) = r^P / r` saves one
  pow on the trig path. Offline test: = the spherical formula in float64 (median rel 1e-4 or better).
  **mandelbulb old/new 1.23-1.49x, julia bulb 1.41-1.50x** (now ~1.3-1.6 ms). Bulb breathe swings the power
  (trig path): no measurable change (1.6-2.6 ms here; 5.2 in the first run under heavier load).
- **Overrelax par (Render page, 1-2, default 1 = classic):** the over-relaxed loop with fallback cuts DE evaluations
  10-30 % offline, but on the GPU it was slower for most scenes (box tunnel 0.74x, lattice 0.68-0.73x, city 0.68-0.70x,
  gyroscope 0.81x, quaternion / KIFS 0.9x: lanes that fall back stretch their SIMD group). So it runs as a separate
  loop only when > 1, and only **apollonian glow** sets it (1.6): old/new **1.15-1.35x**, and it fills the 6 % of
  pixels that ran out of Steps (hit share 0.91 -> 0.98, mean rgb 0.43 -> 0.45; table updated).
- **morph sponge-blobs Stepscale 0.7 -> 0.9:** a mix of two 1-Lipschitz SDFs is 1-Lipschitz, so 0.9 is as safe as
  for the plain scenes; offline hits 0.995-1.0 agree, t within 2 % on 0.98-1.0 (t = 1, 3, 5, 7 s); live 1.15-1.19x.
- **multibrot:** `z^(P-1) = z^P conj(z) / |z|^2` (no second pow / sincos): offline escapes / mu identical, live 1.03x
  (not measurable).
- Tried and reverted: skipping the unused blob / ring setup loops (a runtime bound on the per-thread `BC[16]` fill)
  made every scene **~30 % slower** (city 0.70x) even for scenes that never read it (T-145).
- Parity after the pass (b5): data view hit / escape agreement 1.0, t identical, shaded within 4/255 1.0, check_fx max
  0.0020-0.0034, stats = the table, on scene 1 / 4 / 9, fractal 1-4, fractal2d 5; 19 offline tests green.

| Preset | before -> after (same frames, GPU ms rm, median) | still over? |
|---|---|---|
| fractal 1 mandelbulb | 1.9-2.1 -> 1.3-1.6 | no |
| fractal 3 julia bulb | 1.85-2.0 -> 1.3 | no |
| fractal 2 bulb breathe | 1.6-2.8 (unchanged) | at times (power swing = trig path) |
| scene 4 apollonian glow | 3.7-4.8 -> 3.25-3.6 | yes, slightly: Quality 0.45 or Steps 80 for <= 3 |
| scene 9 morph sponge-blobs | 3.8-4.1 -> 3.3 | slightly: two scenes per step while morphing |
| scene 2 / 5 / 6 / 7 | 1.4 / 2.2 / 1.7 / 2.7 (unchanged code path) | no, at this load |
| fractal2d 5 multibrot traps | 3.7 (1.03x) | yes: Quality 0.6 |
| fractal2d 2 seahorse dive | 4.1-4.9 (unchanged) | yes: perturb interior runs all 600 iterations; Quality 0.3 or Iterations 400 |

Brought home: `node tools/bring_home.mjs --comp /project1/lab/GEN_sdf --from b5 --lane "perf (b5)"`: ops 1141 = b5,
errors 0, parked, **main saved `JazibTD_home.414.toe`** (b5 `Build5.45.toe`).

## FSR 1 upscale (SX-10, lane C, 27 Oct)
Shared GLSL, no COMP: `builders/glsl/fsr_easu.glsl` (EASU, 12 taps, edge-adaptive, de-ringing clamp) and
`builders/glsl/fsr_rcas.glsl` (RCAS, 5 taps, lobe limited so [0, 1] stays [0, 1]; alpha joins the limit unless flat),
ports of AMD FidelityFX FSR 1 (`ffx_fsr1.h`, MIT) float path. Mirror `builders/fsr_logic.py`; tests
`test/test_fsr.py` (14: glslc, constant / flat identity, no ringing, edge 10-90 % width < 0.85 x bilinear on a 1/4
render, PSNR vs the full-res truth > bilinear + 2 dB, RCAS range + HDR untouched). Any consumer: EASU GLSL TOP at the
output size (uniform `uEasu` = out w, h, 1 = EASU / 0 = bilinear), RCAS GLSL TOP after it (`uRcas` = sharpness stops,
denoise, on), both compute, rgba16float.
GEN_sdf consumer: Render page `Upscale` (bilinear / fsr) + `Sharpness`; per module `rm -> easu -> rcas`, `up` (Switch:
rm or rcas) -> fx input 2. Only the picked branch cooks; with fsr, fx reads a full-res picture (its linear read at
texel centres is exact). `upgrade(comp, name)` brings an existing instance up to date (one per exec in main, T-152).

### LIVE CHECKS (FSR; scratch, then main by builder)
- **F1 build:** errors 0 on the instance; `easu` / `rcas` 1080 x 1920 rgba16float; `up` index 0 / 1 follows Upscale and
  `up` resolution = the picked input (rm size / 1080 x 1920).
- **F2 parity:** frozen preset, Upscale fsr, next exec `check_fsr(I)`: easu vs `fsr_logic.easu(live rm)` and rcas vs
  `fsr_logic.rcas(live easu)` max rel <= 4e-3 (rgba16float), easu ringing 0. `check_fx(I)` max <= 3/255 (fx reads `up`).
- **F3 passthrough:** Amount 0 -> out1 = in1 (max 0) with fsr on; Upscale bilinear -> out1 identical to before (the
  old path: `up` = rm).
- **F4 look:** a frozen frame at Quality 1.0 bilinear (= native) vs Quality 0.5 bilinear vs Quality 0.5 fsr: PSNR of
  each vs native; fsr must beat bilinear at the same Quality (or the default stays bilinear).
- **F5 cost:** rm + easu + rcas + fx GPU median (pulled frames, pane off) at Q 0.5 fsr vs rm + fx at Q 1.0 and at
  Q 0.5 bilinear; ms saved = native - fsr. Real fps with only GEN_sdf un-parked.

### Verified live (FSR, scratch TD, 2025.31550, 27 Oct; main's GEN_sdf loaded read-only, `upgrade()` on scene1)
- **F1:** errors 0; easu / rcas 1080 x 1920 rgba16float; `up` follows Upscale and takes the picked input's size (540 x
  960 bilinear, 1080 x 1920 fsr: a Switch TOP passes the selected input's resolution).
- **F2** (menger sponge, frozen t 1 s, Q 0.5): `check_fsr` easu max rel **4.9e-4** (median 1.7e-4), rcas max rel
  **4.9e-4**, easu ringing **0**; `check_fx` max **0.0020** (fx reads `up`).
- **F3:** Amount 0 with fsr -> out1 = in1 max **0**.
- **F4 look** (out1 vs the Q 1.0 native render, frozen): PSNR bilinear / fsr at Q 0.5: sponge 33.2 / 32.3 dB, neon
  lattice 24.2 / 23.7, box tunnel 38.5 / 38.3; at Q 0.35: 31.2 / 30.3, 22.1 / 21.5, 36.2 / 35.9. Mean gradient energy
  (sharpness) vs native: sponge 0.0067 bil / 0.0110 fsr / 0.0094 native, lattice 0.0232 / 0.0316 / 0.0358, tunnel 0.0031
  / 0.0046 / 0.0039. FSR is visibly crisper (edges, lattice rods; crop compare) but also sharpens the aliasing of the
  point-sampled raymarch (stair steps on thin lines), so it does **not** beat bilinear on PSNR. **Default stays
  bilinear** (doc rule F4); FSR is the option for crisper edges.
- **F5 cost** (pulled 150 frames, pane off, only GEN_sdf cooking on scratch; GPU median ms): sponge native Q 1.0
  **5.3-6.4** (rm) / total 6.1-7.6; Q 0.5 bilinear rm 2.4-3.5, total 3.2-4.2; Q 0.5 fsr rm 2.0-2.8 + **easu 0.78-1.05 +
  rcas 0.31-0.35** + fx 0.09-0.15, total 4.1-5.0. Lattice: native 7.2, bilinear 4.6, fsr 4.9. **FSR saves 2.0-2.6 ms
  against the native render and costs +1.1-1.4 ms over bilinear** (EASU ~0.8-1.0 at 1080 x 1920, above the 0.3-0.5
  estimate). Pull fps 59.6-60.1 in every case. A shared-memory tile EASU (one tile load per 8 x 8 group) was **1.4x
  slower** in a paired A/B (0.84 vs 0.60 ms, identical pixels): reverted (T-171).

### LIVE CHECKS (aurora; scratch, then main by builder)
- **A1 add:** `add(C, 'aurora')`: errors 0 (watch for GLSL symbol clashes: `tw curtain adir asky MAXLAYER`), rm at
  Quality 0.5 = 540 x 960, numBlocks = 7 shared flat + 6 = 13.
- **A2 parity:** each preset, frozen (t 1 s), `check(I)` colour view: within 4/255 >= 0.98 (stars and the far
  layers near the horizon may flip a few texels), then View data: within 4/255 >= 0.98.
- **A3 stats:** `stats(I)` (Input black, Blend replace) = `gen_sdf_logic.out_stats` mirror within +-0.03.
- **A4 passthrough:** Amount 0 -> out1 = in1 (0); slot enabled 0 -> 0.
- **A5 cost:** rm + fx GPU median at Q 0.5 (bilinear and fsr) per preset; real fps with only GEN_sdf on. Target <= 3 ms.

### Verified live (aurora, scratch TD, 2025.31550, 27 Oct)
- **A1:** `add` aurora1: errors 0, rm 540 x 960, numBlocks 13. **A2:** presets 1-5 frozen, `check(I, n=400)` colour:
  within 4/255 **1.0**, max <= 1e-4; on 2000 texels of preset 5, 65 % lit, max diff **5.2e-5** (GPU = float32 mirror).
  **A3:** `stats` = `out_stats` mirror: preset 1 (0.0302 0.0861 0.0902 / 0.0302 0.0862 0.0901), preset 3 (0.0286
  0.0741 0.0854 / 0.0286 0.0742 0.0853); `check_fx` max 0.002. **A4:** Amount 0 -> out1 = in1 max **0**.
- **A5 cost** (pulled 150 frames, only GEN_sdf on scratch): preset 1 Q 0.5 bilinear **2.06 ms** total (rm 1.22 GPU,
  fx 0.16), fsr 3.45 (easu 1.56 + rcas 0.25); preset 5 (48 layers) bilinear **2.01** (rm 1.45), fsr 4.04. Pull fps
  57.5-60.4. The curtains are soft, so bilinear stays the default (FSR adds ~1.5 ms for no visible gain).
  Capture: `output/gen_sdf_aurora1_green_curtains.png` (t 6 s).

### In main (lane C, 27 Oct, by builder)
`upgrade()` on scene1, fractal1, fractal2d1 (one exec each), then `add(C, 'aurora', enabled=0)`, in main
(2025.31550): errors 0, 1529 ops, `up` = 0 (bilinear) on all four, scene1 `check_fx` max 0.002; parked, **main saved
`JazibTD_home.570.toe`**. Existing zkit panels show the new Render pars after a panel rebuild (`build_controls`);
their preset slots were re-seeded by `rebuild_shaders` (full state incl. Upscale / Sharpness).

### Verified live (sky, scratch TD, 2025.31550, 27 Oct)
`add` sky1: errors 0, rm 540 x 960. Presets 1-5 frozen: `check(I, n=300)` within 4/255 **1.0**, max <= 5e-4;
`stats` = `out_stats` mirror within 0.0006 on every preset (e.g. golden hour 0.2754 0.3342 0.3696 / 0.2754 0.3342
0.3695, lit 0.265 / 0.266). Cost (day cycle, pulled 150 frames): Steps 16 x Lightsteps 8 (default) **1.89 ms** total
(rm 1.13 GPU), 32 x 16 3.37 (rm 2.63), 8 x 4 1.15 (rm 0.47); pull fps 46-56 (machine busy: 4 TDs).

### Verified live (planet, scratch TD, 2025.31550, 27 Oct)
`add` planet1: errors 0, rm 1080 x 1920 (Quality 1). Presets 1-5 frozen: `check(I, n=400)` within 4/255 **1.0**, max
<= 1e-4; `stats` = `out_stats` mirror (e.g. ringed giant 0.134 0.1051 0.0511 lit 0.097 both). Cost (pulled 150
frames): ringed giant **1.29 ms** total (rm 0.59 GPU at full res, fx 0.18), close pass 1.27; pull fps 55-59. Capture
`output/gen_sdf_planet1_ringed_giant.png` (t 4 s: rings in front of / behind the limb, ring shadow, moon, stars).

### Verified live (dreamcore, scratch TD, 2025.31550, 27 Oct)
**Bug found live:** after `upgrade()` the scene's Scenea menu still had 8 entries (`_pars` skips existing pars), so
preset 10 (Scenea 8) clamped to rings, and the parity check passed anyway (GPU and mirror both read menuIndex 7).
`upgrade()` now refreshes every Menu par's names / labels (`_menus`, value kept): Scenea / Sceneb updated (T-175).
After the fix: Scenea `stairs`, uM0.x 8; `check(I, n=300)` colour within 4/255 **1.0** (max 0), data view hit
agreement **1.0** (270 hits), t identical; `stats` = mirror (0.9057 0.8574 0.8993 / 0.906 0.8573 0.8991); sponge
regression stats 0.1986 0.0891 0.0101 = the table. Cost under a load average of 80-95 (pull fps 38-53, noisy):
Shadowsteps 16 / AO 4 / Q 0.5 5.3-11.3 ms (rm 4.4-10), 8 / 2 / Q 0.5 5.5, **8 / 2 / Q 0.4 3.6 (rm 2.7)** -> the preset now
uses 8 / 2 / Q 0.4; Q 0.35 + FSR 6.0 (easu 1.4 under this load). Capture `output/gen_sdf_scene10_dreamcore.png`.

**Second bring-home (lane C, 27 Oct, by builder):** `upgrade(scene1)` (menus Scenea / Sceneb now list `stairs`),
`add` sky (enabled 0), `add` planet (enabled 0) in main: 6 slots, 2227 ops, errors 0; aurora1 / sky1 / planet1 rm
force-cooked once (compiled, no errors); scene1 `check_fx` max 0.0019; parked, **main saved `JazibTD_home.588.toe`**.
Library `GEN_sdf` 0.2.0 (533 KB).

## Tail modules (lane C2, 27 Oct; BUILD_PLAN_27OCT s3c: SX-14, SX-17, SX-19, SX-20, SX-23)
All clean-room (U8 default: the CC BY-NC-SA Shadertoy originals named in FX7a were not copied), KIND `flat`
(`render2d`, own fixed / fly camera), so the rack's Quality / Upscale (FSR, opt-in) / Still apply; every loop has a
literal cap (T-124). Mirror functions in `gen_sdf_logic.FLAT_TAIL`; data view = (t, hit, x, y) and is compared like
a ray module (hit agreement + t within 2 % rel).

| Module | What | Presets | Audio / beat |
|---|---|---|---|
| ocean (SX-14, 7C-14) | Height-field sea: per octave (Octaves for the march, Detail for normals, cap 8) two crossing wave trains with sharp crests `exp(Choppy (sin - 1))`, the first domain-warped (Warp); octaves rotate, x 1.9 frequency, x 0.42 amplitude, faster (dispersion). Surface found by regula falsi between the eye and Far (Steps, cap 64). Fresnel (Fresnelpow) mix of the reflected sky and Colour A (deep) + Colour B crest scatter (Scatter x height), sun glitter (Specpower), foam on the top crests (Foam, Foamstart), fog to the horizon colour (Bgcolor). Sky: Bgcolor -> Skycolor gradient + sun glow / disk (Sunyaw, Sunpitch, Suncolor, Sunintensity). Camera: Camheight, Glide Flyspeed along the Yaw, Pitch, Yawspeed, Fov. Default Quality 0.5. Data view = (t, hit, height, 1). | 1 sunlit sea, 2 storm, 3 golden sunset, 4 night moon, 5 beat swell | Beatwave / Audiowave -> wave height |
| cloud (SX-17) | Volumetric deck between Base and Top: density = fbm (Octaves, cap 6) of 3D value noise (one 32-bit integer hash per lattice corner: GPU = mirror exactly) x a height profile, over a Coverage threshold, x Density; moved by Windx / Windz / Evolve. Ray clipped to the slab and Maxdist, Steps equal steps (cap 64) from a hashed per-pixel start (Dither); per sample with density one light sample toward the sun (Lightoctaves, Lightstep, Absorb), Beer-Lambert opacity, Henyey-Greenstein silver lining (Silver) + isotropic part, sky ambient rising with height, aerial fade to Bgcolor (Fogdensity); stops when transmittance < 0.01. Sky = Bgcolor -> Skycolor + sun. Camera Camheight, Flyspeed push, Pitch, Yaw, Yawspeed, Fov. Default Quality 0.35. Data view = (t enter, slab hit, transmittance, density sum). | 1 cumulus day, 2 golden hour, 3 fly through, 4 storm deck, 5 above the clouds | Beatlight / Audiolight -> sun light (storm deck: lightning-like flashes on the beat) |
| blackhole (SX-19) | Photon paths integrated per pixel in Schwarzschild units: a = -1.5 Bend Horizon h^2 p / r^5 (h = \|p x v\|), semi-implicit Euler, step Stepsize x r (Steps, cap 256). A step crossing y = 0 between Diskin and Diskout composites the disk front to back: palette by radius (duo orange by default), 1 / r^2, Keplerian Swirl, Bands + Turb wobble, Doppler boost (1 + Doppler beta cos)^3, soft edges, Diskopacity. Captured (r < Horizon) = black; escaped = hashed stars in the bent direction (lensed). Photon-ring glow (Ringglow) near 1.5 Horizon. Tone map 1 - exp(-Exposure c). Orbit camera (Camdist, Campitch, Camyaw, Orbitspeed, Fov). Default Quality 0.5. Data view = (closest r, captured, disk alpha, ring glow). Offline test: shadow radius / horizon = 2.2-3.0 (theory 2.6) with Bend 1, 1 with Bend 0. | 1 interstellar, 2 edge on, 3 top down, 4 blue quasar, 5 close orbit | Beatglow / Audioglow -> disk brightness |
| terrain (SX-20, raymarch route) | Height field = fbm of 2D value noise with analytic derivatives (32-bit integer lattice hash), each octave damped by the summed slope: a += b n / (1 + Erosion \|sum dn\|^2) (gullies, sharp ridges); Octaves for the march (cap 12), Detail for normals (cap 12). Camera glides along Yaw at Camheight over a 3-octave copy of the ground; relaxed march t += Relax (y - h) (Steps, cap 256; hit at 0.002 t). Grass (Colour B) -> rock (Colour A) by slope, snow above Snowline on flat ground, sun with optional terrain soft shadows (Shadowsteps, cap 32), sky ambient, fog to the horizon colour with sun glow, sky gradient + sun. Default Quality 0.4. Data view = (t, hit, ground height, 1). Offline tests: noise derivative = finite difference; hits sit on the ground. | 1 alpine flight, 2 desert dunes, 3 sunset ridges (shadows 12, Q 0.35), 4 snow peaks, 5 night valley | Beatlight -> sun; Audioheight -> mountain height |

### LIVE CHECKS (tail; build TD b4, then main by builder)
- **X1 add:** `add(C, '<module>')` (rack built from `build()` on b4, no tox loads, T-179): errors 0 on the instance (watch
  for GLSL symbol clashes with TD's compute header), rm = Quality x 1080 x 1920 rgba32float.
- **X2 parity:** each preset frozen (t 1 s), next exec `check(I, n=300)`: colour within 4/255 >= 0.95 (march
  flips on silhouettes / far grazing rays are the expected miss); View data: hit agreement >= 0.97, t within 2 % >= 0.95.
- **X3 stats:** `stats(I)` (Input black, Blend replace) = `out_stats` mirror within +-0.03 (table below).
- **X4 passthrough:** Amount 0 -> out1 = in1 max 0; slot enabled 0 -> 0.
- **X5 presets full state:** after `preset(I, k)` the module's own pars equal `module_pars(M, preset)` (T-175 rule 2).
- **X6 cost:** rm + fx GPU median (pulled frames, pane off, only GEN_sdf un-parked) at the default Quality, bilinear and
  fsr; real fps. Aim <= 3 ms; if over, the Quality / Steps that meet it go into the preset or the table.

### Verified live (tail, build TD b4, 2025.31550, 27 Oct; GEN_sdf built on b4 from `build(first='ocean')` + `add`)
Load average 15-62 (5 other TDs busy). New modules first enabled at Quality 0.2-0.25, raised after clean frames (T-194).
- **X1:** ocean / cloud / blackhole / terrain / fractal added, errors 0, no GLSL symbol clash; rm 540 x 960 (ocean),
  378 x 672 (cloud), 432 x 768 (blackhole, terrain) rgba32float.
- **X2 parity, every preset, frozen t 1 s, n 300:** colour within 4/255 **1.0** on all 24 (max <= 0.002); data view
  hit agreement **1.0**, t within 2 % **1.0** (fractal 7-10 too). The integer-hash noises (cloud 3D, terrain 2D) match
  the mirror exactly.
- **X3 stats = mirror** (Input black, Blend replace) within 0.002 on every preset:

| Module | Preset | rm | Mean rgb (live) | Lit |
|---|---|---|---|---|
| ocean | 1 sunlit sea | 540x960 | 0.422 0.520 0.604 | 0.548 |
| ocean | 2 storm | 540x960 | 0.239 0.283 0.302 | 0.008 |
| ocean | 3 golden sunset | 540x960 | 0.510 0.375 0.325 | 0.305 |
| ocean | 4 night moon | 540x960 | 0.052 0.103 0.161 | 0.007 |
| ocean | 5 beat swell | 540x960 | 0.410 0.508 0.593 | 0.539 |
| cloud | 1 cumulus day | 378x672 | 0.689 0.712 0.781 | 0.943 |
| cloud | 2 golden hour | 378x672 | 0.881 0.664 0.514 | 0.867 |
| cloud | 3 fly through | 378x672 | 0.820 0.817 0.836 | 1.000 |
| cloud | 4 storm deck | 378x672 | 0.349 0.340 0.339 | 0.086 |
| cloud | 5 above the clouds | 378x672 | 0.725 0.704 0.723 | 0.913 |
| blackhole | 1 interstellar | 432x768 | 0.107 0.065 0.031 | 0.026 |
| blackhole | 2 edge on | 432x768 | 0.118 0.074 0.035 | 0.035 (mirror) |
| blackhole | 3 top down | 432x768 | 0.146 0.071 0.149 | 0.008 (mirror) |
| blackhole | 4 blue quasar | 432x768 | 0.166 0.223 0.287 | 0.142 (mirror) |
| blackhole | 5 close orbit | 432x768 | 0.126 0.085 0.026 | 0.035 |
| terrain | 1 alpine flight | 432x768 | 0.361 0.413 0.392 | 0.274 |
| terrain | 2 desert dunes | 432x768 | 0.545 0.478 0.427 | 0.588 |
| terrain | 3 sunset ridges | 378x672 | 0.357 0.221 0.200 | 0.212 |
| terrain | 4 snow peaks | 432x768 | 0.397 0.422 0.404 | 0.263 |
| terrain | 5 night valley | 432x768 | 0.131 0.175 0.170 | 0.008 |
| fractal | 7 kifs glow orbit | 378x672 | 0.201 0.270 0.308 | 0.092 |
| fractal | 8 box cathedral | 378x672 | 0.819 0.497 0.390 | 0.604 |
| fractal | 9 julia glow | 378x672 | 0.099 0.489 0.412 | 0.315 |
| fractal | 10 power coils | 302x538 | 0.247 0.313 0.339 | 0.192 |

- **X4:** Amount 0 -> out1 = in1 max **0** and slot enabled 0 -> out1 = img_src max **0** (ocean, cloud, blackhole,
  terrain). **X5:** after preset 1 then k, every module par = `module_pars` (0 mismatches; ocean 2/3, cloud 4/5,
  blackhole 4/5, terrain 3/4).
- **X6 cost** (`perf_pull`, 150 pulled frames, only GEN_sdf cooking on b4, other lab COMPs parked; total = every op
  of the instance, GPU + CPU median ms; rm GPU in brackets; pull fps):

| Preset | bilinear total (rm GPU) | fsr total | pull fps |
|---|---|---|---|
| ocean 1 sunlit sea | **1.45** (0.73) | 2.60 (easu 0.60 + rcas 0.21) | 59.3 |
| ocean 2 storm | 1.58 (0.82) | | 53 |
| cloud 1 cumulus day | **2.13** (1.35) | 3.49 | 39-40 |
| cloud 3 fly through (Steps 32) | 2.74 (2.06); 3.2 at Steps 40 before | | 49 |
| cloud 4 storm deck | 2.26 (1.42) | | 55 |
| blackhole 1 interstellar | **1.61** (1.03) | 3.66 | 53-59 |
| blackhole 5 close orbit | 2.45 (1.73) | | 60 |
| terrain 1 alpine flight | **2.23** (1.67) | 4.03 | 58 |
| terrain 3 sunset ridges (shadows) | 2.33 (1.65) | | 52 |
| terrain 4 snow peaks | 2.77 (2.04) | | 52 |
| fractal 7 kifs glow orbit | 1.23 (0.59) | | 57 |
| fractal 8 box cathedral | 2.47 (1.63) | | 54 |
| fractal 9 julia glow | 1.71 (0.90) | | 50 |
| fractal 10 power coils (Iterations 7, Q 0.28) | 2.82 (2.17); 5.2 at 10 it / Q 0.35 before | | 58 |

  Every default and preset is under the 3 ms aim; FSR stays opt-in (+1.2-2 ms, soft subjects gain little).
- **Live fixes:** blackhole disk bands wound up over time (Keplerian shear grows with T: fine moire after minutes,
  capture at t ~ 200 s) -> two sheared copies on a 4-unit cycle, cross-faded; fractal 7 with a rotating fold
  (Kifsspeed) or a fly path left the frame empty after ~30 s -> static fold, wander orbit. b4 hang during the first
  blackhole pass (T-194): defaults lowered to Quality 0.4 / Steps 64.
- Captures (b4 out1, 1080 x 1920): `output/gen_sdf_ocean1_sunlit_sea.png`, `output/gen_sdf_cloud2_golden_hour.png`,
  `output/gen_sdf_blackhole1_interstellar.png`, `output/gen_sdf_terrain1_alpine_flight.png`.

### In main (lane C2, 27 Oct, by builder)
Main quiet (no main execs since 00:20Z, no GEN_sdf writes by other lanes since 23:45Z); `lane.py add`; un-park; one exec
each: `add(C, 'ocean' | 'cloud' | 'blackhole' | 'terrain', enabled=0)`, `upgrade(C, 'fractal1')` (presets 7-10 seeded,
11 preset rows); each new rm force-cooked once (compiled, errors 0); terrain1 preset 1 frozen `check` within 4/255
1.0 (max 0); layout; parked; **main saved `JazibTD_home.699.toe`** (GEN_sdf 3623 ops, 10 slots: scene1 enabled, the
rest enabled 0).

## Not done / open
- No baked-loop mode (FX5 G14 suggested record-to-movie for heavy fractals): use `td_record` / Movie File Out by hand.
- No refraction / dispersion materials (P_realtime_3d_looks P4); no multiple lights; no scene assembler from DAT
  snippets (one fixed shader per module, scenes by menu, so no recompiles).
- Perturbation for Burning Ship / Tricorn / Multibrot is not built (float only); Kleinian / Apollonian 3D fractal
  types not in `fractal` (Apollonian lives in `scene`).

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.742).
