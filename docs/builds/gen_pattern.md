# gen_pattern: GEN_pattern rack + 17 one-pass generator modules (live in main, 26-27 Oct 2026, TD 2025.31550)

`/project1/lab/GEN_pattern`. FX0 row "GEN_pattern" (backlog ranks 37, 38, 64, 65, 68, 80): research cards FX5 G06
truchet, G17 opart, G07 wallpaper, G28 domainwarp, G29 gyroid, G27 cymatics, E7/G30 split, G20/E2 barcode, E5/G35
columns, G16 + FX4 G-KALEIDO2 / G-INFZOOM kaleido2 / droste / infzoom. Everything below was written and tested
offline (no TD tools); the LIVE CHECKS section is the job for the live lanes, with the numbers they must hit.

**Status: live on 2025.31550 (built in b3, in the main .toe): all 12 modules verified, see "Verified live". 18 offline
tests; every shader compiles with `glslc` (OpenGL target, TD-like prelude).**

## Design (lean, copied from FX_glitch, not abstracted)
Same rack as `FX_glitch` (`docs/builds/fx_glitch.md`): `slots` table (`name module enabled order mix`), per slot
module COMP -> `<name>_mix` (Cross) -> `<name>_slot` (Switch 0 bypass / 1 module / 2 mix), `panic`, `out1`. The
differences, each because ALL 12 modules use it today (no-bloat rule):
- **Generator slot.** A module file is data only (`PAGES`, `DEFAULTS`, `PANEL_PAGES`, `PRESETS`, `UNIFORMS`, `GLSL`,
  optional `CHECK`); the rack builds every module's network itself: `in1` -> `fx` (ONE compute GLSL pass, docked
  `fx_compute`, `format useinput`, res = input, `inputextenduv hold`, `inputfiltertype linear`) -> `out1`, plus the
  module clock `clock` (Constant CHOP: Speed x (1 + Audiospeed x level)) -> `clock_int` (Speed CHOP = module time,
  no jump when Speed changes). Single-pass compute = no T-46 tearing; Amount 0 = `texelFetch` -> store = exact.
- **Two kinds.** `gen` modules write `void gen(vec2 q, vec2 P, vec4 src, out float v, out float k)`: v = pattern
  (0..1 mask / intensity), k = palette coordinate; the shared code turns that into colour (Colour page) and blends it
  over the slot input (Blend: Replace = Bgcolor -> palette by v, Add, Screen, Multiply, Difference, Alpha out
  premultiplied for Resolume overlays). `warp` modules (kaleido2, droste, infzoom) write `vec4 warp(vec2 P, vec4 c)`
  and remap the slot input (chain them after a generator, or over the background picture).
- **Background.** Rack `Input`: auto (in1 if wired, else black) / black (`bg` Constant TOP at Resw x Resh,
  default 1080x1920) / live / test clip. Panic = background straight to out1.
- **Drive (rack page):** `drive` Constant CHOP = `beats`, `bpm`, `level`. Beats come from the internal clock
  (`drive_rate` Bpm/60 -> `drive_beats` Speed CHOP; Bpm or a Bpm CHOP channel, e.g. `AU_features/out1` `bpm`) or a
  beat CHOP (`Beatsource` chop: `beat_count` + `beat_phase` of `AU_features/out1`); level = `Audiochop`/`Audiochan`
  (e.g. `AC_audio/out_ctl` `low`). `Resync` pulse (Parameter Execute `drive_pexec`) = beat 1 now.
- **Drive (module page, all modules):** Speed, Phase (s), Audiospeed (audio -> clock rate), Audiogain (audio -> the
  module's look target, see table), Beatevery (step every N beats, 0 off), Beatgain + Beatdecay (pulse ENV =
  Beatgain exp(-age/decay) after each step), Seed. Shader globals: `T STEP AGE ENV LEVEL SEED PX RES`.
- **Space (generators):** Scale (units per screen height), Rotate, Rotspeed, Centre, Drift x/y (units/s).
- **Colour (generators):** Palette duo (A -> B ping-pong) / solid A / rainbow / fire / ice / gold / neon / sunset
  (IQ cosine), Spread, Offset, Huecycle (/s), Colour A, Colour B, Background, Blend.
- No limiter, no flash or frequency caps anywhere (user rule; FX5's `Safe` pars deliberately not built).

Files: `builders/gen_pattern.py` (rack, shared GLSL, specs, freeze/check/stats), `builders/gen_pattern_<module>.py`
x 12, `builders/gen_pattern_logic.py` (pure Python mirror of every shader line: `expect(module, U, x, y, W, H, src)`
= the rgba the shader writes; `uniforms(spec, pars, ...)` = the uniform expressions offline), `test/test_gen_pattern.py`
(18 tests: rack maths, specs, uniforms declared + used, glslc compile of all 12, hash / passthrough / blends, maths
invariants: quasicrystal pi/N symmetry, Chladni zero on x = y, kaleido mirror, droste self-similarity, infzoom period,
every preset non-flat). Run: `python3 -I -m unittest discover -s test -p 'test_gen_pattern.py'` (~5 s).

Uniform spec mini-language (one spec, two readers): `{Par}` value, `{Par#}` menu index, `$t` (clock_int + Phase),
`$step`, `$age`, `$level` (rack drive), `$W` `$H` (`me.par.resolutionw/h`, never `me.width`, T-117 (2)).
`td_expr()` turns it into TD expressions, `gen_pattern_logic.uniforms()` evaluates it offline.

## Modules
| Module | Kind | What | Audio (Audiogain) | Beat pulse / step | Est. GPU ms 1080x1920 |
|---|---|---|---|---|---|
| truchet | gen | Smith arcs / diagonal maze / triangles / 2-colour arc regions, multi-scale Levels + Subdivide | line width | width; steps flip Flipshare of tiles (+ Fliprate Hz) | 0.2-0.4 |
| opart | gen | 1-3 AA gratings (lines circles dots checker rays) xor/mul/diff/add/max; Riley / bulge / twist | warp amount | phase kick; Beatinvert per step | 0.2-0.4 |
| wallpaper | gen | quasicrystal N waves (+ Bands), Hankin stars 8-fold / 12-fold (Theta), ring motifs p4m / p6m | line width | Theta +15 deg / phase kick | 0.2-0.6 (N 16 ~1) |
| domainwarp | gen | IQ warped fbm Depth 1-3, Octaves, Evolve, marble Bands, Tint, Contrast | warp amount | evolve kick | 0.8-2 (Depth 3 x 8 oct most) |
| gyroid | gen | TPMS slices gyroid / Schwarz P / diamond / Neovius: constant-px contours, bands, glow; Twist | iso level | line width | 0.2-0.4 |
| cymatics | gen | Chladni square (-/+), triangular, radial; sand + grains or field; manual n/m (+ Wobble) or 12-mode beat list with Morph | sand width | brightness; steps change mode | 0.2-0.4 |
| split | gen | per-pixel BSP (<= 10 levels), seams slide in per generation, re-seed after Hold; fill / outline / both, Gap, newborn glow | brightness | Beatgrow generations per step | 0.2-0.4 |
| barcode | gen | run-length bars / bit grid / input-luma scan, bands scroll opposite ways, Rate re-roll, Vertical | scroll speed | density; steps re-roll; Beatinvert | 0.1-0.3 |
| columns | gen | light beams (5-tap halo, soft top, haze) / LED meter / dot field; heights = wave + jitter + audio + beat | column heights (per-column weight) | heights; steps re-roll jitter | 0.3-0.5 |
| kaleido2 | warp | wedge / squares / diamonds / hex12 (td-port Kaleido folds) + fly's-eye hex / rect (Lenszoom, Cellshift, Vignette) | zoom | +30 deg kick | 0.1-0.3 |
| droste | warp | log-polar Droste spiral (Ratio, Strands, Twist; 0 = tunnel), Zoomspeed copies/s | rotation + radius | quarter-copy zoom kick | 0.1-0.3 |
| infzoom | warp | Layers cross-faded copies at Zoomstep^(i+f) (one pass, no feedback), Layerrot | (Audiospeed) | half-layer zoom kick | 0.2-0.5 (Layers 8 ~0.8) |
Estimates are from the FX5 cards and the FX_glitch costs (a one-pass compute ~0.15-0.5 ms at 1080x1920 on this
Mac, T-100/T-108); the live lane measures and replaces them. Every module has 4-5 presets (`PRESETS` in its file).

## LIVE CHECKS (live lanes; ~15 min per module)
Rules that apply: `td_guide` + `td_status` first; `python3 tools/lane.py add GEN_pattern "<lane>"` (remove at the
end); un-park only GEN_pattern; one structural change per call + `td_errors` (T-31); state reads in a separate exec
>= 3 frames after the change (T-116 (4), T-117 (4)); pixel reads only on a frozen, stable picture (T-74);
`td_checkpoint` after each verified module; everything ends in the main .toe (CLAUDE.md). Multiple TDs: lanes may
verify on the scratch TD under a lane-owned parent (`build('/project1/<lane>', first='<module>')`, T-117 (5)) and then
`add` the module to the main `/project1/lab/GEN_pattern`; the main rack is built once, by the first lane, before any
`add` (rack edits from two lanes at once would race on `slots` + layout).

Exec preamble (every call): `ns = dict(globals()); exec(open('<repo>/builders/gen_pattern.py').read(), ns)`;
`C = '/project1/lab/GEN_pattern'`; `I = C + '/<module>1'`.

**Step 0, once (first lane, ~8 min):** `ns['build']('/project1/lab')` -> rack + `truchet1`. Expect `td_errors`
clean on C and C/truchet1 (watch for a GLSL compile error naming a redefined symbol: TD's compute header could
define one of `TAU PI T STEP AGE ENV LEVEL PX SEED RES h2 h3 band stroke rot2 tri` - rename it in gen_pattern.py and
note it in LEARNINGS), `wires_changed` 6 + 3 on first build, a second `rewire(op(C))` -> 0, `slots` = 1 row,
`drive` channels `beats bpm level`, beats rising 2.0 per s at Bpm 120 (read `op(C+'/drive')['beats']` twice 1 s apart
in separate execs), `Resync` -> beats back near 0. `td_layout` ok, viewers on.

**Per module (A-G):**
- **A Add** (skip for truchet): `ns['add'](C, '<module>')` -> `added <module>1`, 7 wires changed; `td_errors` clean;
  `op(I+'/fx').seq.vec.numBlocks` = len(spec) (gen 9 + module, warp 3 + module; opart 15 is the largest).
- **B Preset + input:** generators: rack `Input` = black; warps: put the slot after a frozen generator (default
  chain order does this) or set `Input` = test. `ns['preset'](I, 1)`.
- **C Freeze:** `ns['freeze'](I)` (t = 1 s, beats 0; split: t 6, beats 5 = its `CHECK`). Next exec:
  `ns['check'](I)` -> **within_tol >= 0.97, median <= 0.004 (1/255), p95 <= 0.012** (warps: within_tol >= 0.95;
  8-bit bilinear weights). Record `flip_rows` (numpy row order) once in LEARNINGS. A miss means the GLSL and the
  mirror disagree: compare `uniforms` in the reply with `gen_pattern_logic.uniforms(...)` first, then the module code.
- **D Expected numbers (generators):** `ns['stats'](I, flip_rows=<from C>)` for each preset (set preset, freeze,
  read in a separate exec) -> mean rgb within +-0.01 and lit within +-0.01 of the table below; the named pixels within
  3 levels unless one sits on an AA edge. Barcode `scan` with Input black is all 0 by design: check it with Input
  test (check() only).
- **E Exact passthrough:** Amount 0 -> numpy max abs diff `out1` vs `in1` of the instance = **0**; slot `enabled` 0
  and `mix` 0 -> rack `out1` = `img_src` (diff 0); Panic -> diff 0 vs `img_src`.
- **F Drive:** `ns['unfreeze'](I)`; rack Bpm 120, module Beatevery 1, Beatgain 1: `ns['read_uniforms'](op(I+'/fx'))`
  twice 1.0 s apart -> `uDrv.y` (step) +2, `uDrv.z` (age) in 0..0.5; ENV after a step decays by e per Beatdecay.
  With `Audiochop` = `AC_audio/out_ctl` (or any CHOP) `uDrv.w` follows the channel. Speed 0 -> picture holds
  (`uDrv.x` constant); Speed 2 -> `uDrv.x` advances 2 s per s with no jump.
- **G Cost + fps + save:** pane off GEN_pattern; pull `out1` 120 frames and sum cpu+gpu of the instance's ops whose
  `cookAbsFrame` equals out1's (T-102 method) -> **<= 3 ms median** (estimates in the module table); project real fps
  60 with GEN_pattern alone un-parked (pull-only run, T-111 (4)). Then one `td_screenshot` of the instance out1
  (T-114 (4)), `td_layout` ok, `td_checkpoint {path: C}`, `ns['unfreeze'](I)`, leave the slot `enabled` 0 unless the
  user wants it on, save, park, `lane.py remove`.

Over budget: lower the preset's cost knob first (domainwarp Octaves / Depth, wallpaper Waves, infzoom Layers,
columns Haze); a per-module Quality / half-res option comes only when a module needs one (fx_glitch rule).

### Expected numbers (generators; frozen t = 1 s, beats 0, Bpm 0, no audio, black background, 1080x1920)
1000 `gen_pattern_logic.sample_points(1080, 1920)` (seed 7); lit = luma > 0.5; named pixels (TD x, y; y up)
(540, 960) / (100, 1700) / (901, 333) as 0-255 rgb. Split uses its CHECK (t 6, beats 5). Regenerate after any
change: `uniforms()` + `expect()` per preset (the test file's `U_for` shows the call).

| Module | Preset | Mean rgb | Lit | Named pixels |
|---|---|---|---|---|
| truchet | 1 weave | 0.236 0.236 0.236 | 0.234 | 0,0,0 / 255,255,255 / 0,0,0 |
| truchet | 2 maze | 0.170 0.170 0.170 | 0.162 | 0,0,0 / 0,0,0 / 0,0,0 |
| truchet | 3 bridges | 0.226 0.159 0.051 | 0.132 | 0,0,0 / 255,200,81 / 0,0,0 |
| truchet | 4 quilt | 0.248 0.212 0.274 | 0.185 | 10,59,120 / 6,220,152 / 52,254,74 |
| truchet | 5 knots | 0.541 0.541 0.541 | 0.540 | 255,255,255 / 0,0,0 / 0,0,0 |
| opart | 1 riley waves | 0.532 0.527 0.516 | 0.526 | 20,20,23 / 240,237,230 / 20,20,23 |
| opart | 2 vasarely | 0.508 0.503 0.493 | 0.496 | 20,20,23 / 20,20,23 / 240,237,230 |
| opart | 3 circle moire | 0.502 0.497 0.487 | 0.489 | 240,237,230 / 20,20,23 / 240,237,230 |
| opart | 4 line pair | 0.273 0.271 0.272 | 0.224 | 20,20,23 / 20,20,23 / 20,20,23 |
| opart | 5 dots beat | 0.442 0.438 0.431 | 0.418 | 20,20,23 / 240,237,230 / 240,237,230 |
| wallpaper | 1 quasi 7 | 0.079 0.375 0.297 | 0.166 | 208,129,11 / 17,29,91 / 7,53,99 |
| wallpaper | 2 quasi bands | 0.482 0.420 0.307 | 0.447 | 39,31,17 / 73,71,67 / 3,3,2 |
| wallpaper | 3 star 8 | 0.139 0.123 0.094 | 0.141 | 0,0,0 / 0,0,0 / 0,0,0 |
| wallpaper | 4 star 12 | 0.153 0.131 0.092 | 0.160 | 0,0,0 / 0,0,0 / 0,0,0 |
| wallpaper | 5 rings beat | 0.112 0.172 0.144 | 0.172 | 0,0,0 / 0,0,0 / 0,0,0 |
| domainwarp | 1 marble | 0.294 0.280 0.263 | 0.178 | 92,88,82 / 187,181,170 / 21,20,19 |
| domainwarp | 2 smoke (Octaves 4 after live cost) | 0.132 0.277 0.443 | 0.157 | 102,184,234 / 16,25,51 / 5,50,119 |
| domainwarp | 3 oil | 0.189 0.324 0.387 | 0.208 | 46,127,19 / 100,243,29 / 29,39,137 |
| domainwarp | 4 lava | 0.273 0.169 0.043 | 0.135 | 90,48,0 / 158,91,1 / 6,3,19 |
| domainwarp | 5 beat ink | 0.333 0.374 0.320 | 0.336 | 158,199,128 / 16,85,85 / 0,50,72 |
| gyroid | 1 contours | 0.034 0.036 0.036 | 0.029 | 0,0,0 / 0,0,0 / 0,0,0 |
| gyroid | 2 cells | 0.811 0.656 0.376 | 0.842 | 242,179,64 / 247,206,131 / 247,208,138 |
| gyroid | 3 diamond glow | 0.004 0.024 0.059 | 0.000 | 3,14,30 / 2,8,15 / 0,0,0 |
| gyroid | 4 neovius twist | 0.355 0.310 0.230 | 0.331 | 0,0,0 / 13,12,10 / 1,1,1 |
| gyroid | 5 beat lines | 0.063 0.089 0.085 | 0.084 | 0,0,0 / 0,0,0 / 0,0,0 |
| cymatics | 1 sand plate | 0.135 0.112 0.068 | 0.139 | 242,201,121 / 0,0,0 / 0,0,0 |
| cymatics | 2 beat modes | 0.114 0.095 0.057 | 0.111 | 242,201,121 / 0,0,0 / 24,20,12 |
| cymatics | 3 radial | 0.102 0.085 0.051 | 0.090 | 242,201,121 / 0,0,0 / 0,0,0 |
| cymatics | 4 field | 0.126 0.378 0.257 | 0.241 | 255,66,66 / 3,120,84 / 14,145,68 |
| cymatics | 5 wobble | 0.064 0.053 0.032 | 0.059 | 242,201,121 / 0,0,0 / 0,0,0 |
| split | 1 parting | 0.272 0.796 0.384 | 0.850 | 7,221,150 / 124,241,18 / 140,232,10 |
| split | 2 beat split | 0.335 0.204 0.214 | 0.054 | 110,5,55 / 95,0,51 / 102,99,51 |
| split | 3 mondrian | 0.320 0.218 0.170 | 0.033 | 95,34,32 / 64,12,21 / 90,73,52 |
| split | 4 wire | 0.033 0.033 0.033 | 0.032 | 0,0,0 / 0,0,0 / 0,0,0 |
| split | 5 deep | 0.297 0.210 0.128 | 0.000 | 70,62,51 / 70,30,2 / 121,62,2 |
| barcode | 1 barcode wall | 0.500 0.500 0.500 | 0.500 | 0,0,0 / 0,0,0 / 0,0,0 |
| barcode | 2 bit grid | 0.367 0.367 0.367 | 0.367 | 0,0,0 / 0,0,0 / 0,0,0 |
| barcode | 3 scan | 0.000 0.000 0.000 | 0.000 | (black input; check with Input test) |
| barcode | 4 binary rain | 0.143 0.098 0.155 | 0.000 | 0,0,0 / 0,0,0 / 0,0,0 |
| barcode | 5 beat flip | 0.634 0.634 0.634 | 0.634 | 0,0,0 / 255,255,255 / 0,0,0 |
| columns | 1 light columns | 0.309 0.365 0.431 | 0.399 | 97,117,142 / 0,0,0 / 63,102,153 |
| columns | 2 vu meter | 0.038 0.098 0.031 | 0.109 | 0,0,0 / 14,3,2 / 0,0,0 |
| columns | 3 dot field | 0.104 0.115 0.128 | 0.071 | 0,0,0 / 22,1,13 / 5,5,0 |
| columns | 4 beat beams | 0.366 0.436 0.520 | 0.351 | 72,88,107 / 6,6,6 / 46,76,116 |
| columns | 5 haze wall | 0.161 0.246 0.334 | 0.070 | 0,17,49 / 137,158,162 / 53,78,84 |

### Warp modules (kaleido2, droste, infzoom)
No fixed numbers (they depend on the input): `check()` samples the instance's own `in1` with the mirror's bilinear,
so the check is exact for any input. Recipe: chain `truchet1` (preset 1, frozen) -> `<warp>1` (preset 1, frozen) and
run `check(I)`; then once with Input test (clip paused by freeze). Visual sanity in the capture: kaleido2 mandala =
8 mirrored wedges around the centre; droste escher = the input spiralling in, one copy every turn; infzoom dive =
nested copies, no visible seam between layers when unfrozen (watch 5 s: the loop period is 1 / Zoomspeed = 5 s).

## Verified live (26 Oct, 2025.31550, built in build TD b3, brought home into main)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Method: `check` / `stats` per preset in chained `run()` steps (preset + freeze, read 6 frames later); passthrough
(Input test, clip paused) Amount 0 / slot enabled 0 / mix 0 / Panic: numpy max abs diff; cost = 120 forced out1 pulls,
sum cpu+gpu of the instance TOPs cooked that frame (T-102), pane off the COMP, plus the median GPU time of `fx`.
`flip_rows` = **False** (numpy row 0 = TD y 0). Warps: chained after `truchet1` (preset 1, frozen) for every preset,
then once over the test clip (paused). b3 shared the Mac with 3 other busy TDs (main + b2 + scratch), so GPU numbers
are noisy (p90 2-9 ms from other TDs; the first sample after a pane switch is a 300-700 ms viewer rebuild).
Live fixes: presets apply the full state (T-124 (1)); droste scale 1/cos (T-124 (5)); domainwarp smoke Octaves 6 -> 4
(4.4 ms fx GPU -> 2.2).

**fps (corrected, T-124 (4)):** the per-module "60 fps" first written here came from absTime frames per wall second,
which follows the wall clock under realTime. Real frames (Execute DAT onFrameStart counter, 5 s): **b3 53.6 fps with
GEN_pattern parked, 52.4-55.6 fps with it on** (truchet slot, pane off the rack) = no measurable cost from the rack;
the ceiling is the machine load. With the pane ON the rack every module's viewer pulls its out1 (T-111 (5)): all 12
cooking = 43 fps. Close the pane / viewers on the rack in a show.

- **Step 0 rack:** `td_errors` clean (no GLSL symbol clash), first build 9 wires (6 + 3), second `rewire` 0, `slots`
  1 row, `drive` = beats bpm level; beats +2.97 in 1.5 s at Bpm 120 with the pane on the COMP (2.0/s; unpulled it
  lags, T-124 (2)); Resync -> 0.5 a few frames later; Audiochop = a Constant `low` 0.3 -> drive level and uDrv.w 0.3.
  Every `add` = 7 wires, td_errors clean, numBlocks = spec (opart 15, wallpaper 11, domainwarp 11, gyroid 12,
  cymatics 12, split 13, barcode 13, columns 13, kaleido2 7, droste 6, infzoom 5).
- **All 12: check within_tol 1.0 for every preset** (max 0.002-0.0036, i.e. < 1 level), **stats = the table** (every
  mean within 0.002, lit within 0.002), **passthrough Amount 0 / enabled 0 / mix 0 / Panic = 0** (module on 0.77-1.0).
- **Drive (truchet, rack-shared code):** Beatevery 1 Bpm 120: step +2 and T +1.0 in 1 s, age 0.467 both reads;
  Speed 2: T +2.0 per s; Speed 0: T holds.

| Module | Cost preset | Cost median ms (fx GPU) | Capture (`output/`) |
|---|---|---|---|
| truchet | 5 knots | 1.06 | `project1_lab_GEN_pattern_truchet1_out1_2026-10-26T15-33-48-243Z.png` |
| opart | 1 riley | 0.63 | `project1_lab_GEN_pattern_opart1_out1_2026-10-26T15-41-54-258Z.png` |
| wallpaper | 1 quasi 7 | 1.49 | `project1_lab_GEN_pattern_wallpaper1_out1_2026-10-26T15-43-48-871Z.png` |
| domainwarp | 2 smoke (Oct 4) / 1 marble | 2.60 (2.24) / 3.5-3.7 (3.27) | `project1_lab_GEN_pattern_domainwarp1_out1_2026-10-26T15-46-21-180Z.png` |
| gyroid | 4 neovius | 1.12 (0.73) | `project1_lab_GEN_pattern_gyroid1_out1_2026-10-26T15-47-05-650Z.png` |
| cymatics | 2 beat modes | 1.52 (0.99) | `project1_lab_GEN_pattern_cymatics1_out1_2026-10-26T15-47-40-022Z.png` |
| split | 5 deep | 1.96 (1.06) | `project1_lab_GEN_pattern_split1_out1_2026-10-26T15-48-13-194Z.png` |
| barcode | 1 wall | 0.66 (0.28) | `project1_lab_GEN_pattern_barcode1_out1_2026-10-26T15-48-52-731Z.png` (scan over test: check max 0) |
| columns | 5 haze wall | 1.14 (0.66) | `project1_lab_GEN_pattern_columns1_out1_2026-10-26T15-49-26-931Z.png` |
| kaleido2 | 3 hex | 0.55 (0.25) | `project1_lab_GEN_pattern_kaleido21_out1_2026-10-26T15-50-26-070Z.png` (instance name `kaleido21`) |
| droste | 3 double | 0.57 (0.25) | `project1_lab_GEN_pattern_droste1_out1_2026-10-26T15-52-30-924Z.png` (after the seam fix) |
| infzoom | 2 spiral | 0.92 (0.65) | `project1_lab_GEN_pattern_infzoom1_out1_2026-10-26T15-53-13-451Z.png` |

domainwarp marble (Depth 2 x 5 octaves) measured 3.3 ms fx GPU under the shared-GPU load, just over the 3 ms aim; its
preset is unchanged (lower Octaves to 4 if it matters in a show). Networks: `output/window_TouchDesigner_2025.31550_Users_vyro_Docu_2026-10-26T15-41-55-030Z.png`
(2 modules), `..._2026-10-26T15-53-36-971Z.png` (all 12); layout check ok (47 ops, no overlaps / back wires).
- **Brought home** after truchet + opart (669 ops, errors 0, `JazibTD_home.312.toe`) and at the end: main
  `/project1/lab/GEN_pattern` 3359 ops = b3 (td_bring_home timed out at 60 s but the load finished, T-124 (6)), errors
  0, layout ok, truchet preset 5 re-checked in main (within_tol 1.0, stats 0.5415 / 0.540 = table), parked, main saved
  `JazibTD_home.322.toe`. Final rack: truchet1 enabled, the other 11 slots enabled 0, Input auto, Bpm 120.
  Checkpoint `output/checkpoints_b3/GEN_pattern/GEN_pattern_20261026-205335.tox`; transfer `output/transfer/GEN_pattern.tox`.

## Lane A wave (27 Oct 2026, BUILD_PLAN_27OCT lane A, TD b3): new modules + shared palette
Offline first (module file, mirror in `gen_pattern_logic.py`, tests incl. glslc), then live on b3, then home into main
by builder (one module per exec, T-152). Rack additions, opt-in per module so the 12 first modules keep their shader
text byte-identical (no recompile, T-154):
- **Shared palette (W1-B, `docs/builds/palette_convention.md`)** for modules with `PAL = True`: Colour page Palette
  gets `Shared palette` (index 8 -> `pxPal(k)`, `glsl/px_palette.glsl` prepended); a **Palette** page (Palsource =
  custom hex list / 8 stop presets / 7 Lospec, Palmode gradient / steps / cycle, Palinterp rgb / OKLab, Palreverse,
  Palshift, Paldrive manual / bpm_step / bpm_cycle / audio, Palevery beats, Palgain) feeds the module's `pal` Script
  CHOP (`palmap` = palette_map_logic text, `pal_callbacks`) -> Arrays `uPal[16]`, and `uPalCtl` (count, shift +
  drive, mode, interp) as a normal uniform (`PAL_CTL_SPEC`; new tokens `$beats $bpm $palcount`).
- **Hit ring** for modules with `HITS = n`: Hits page `Hit0..Hit<n-1>` (stamps in module time, clock_int + Phase) +
  `Hitnext`; `hit_pexec` (Hit / Clear pulses) and `hit_chopexec` (rising edge of `Hitchan` on `Hitchop`) write them;
  stamps later than now are voided both in the DAT and in the uniform expression (T-162). No limiter.
- `freeze()` also sets the module's `CHECK['pars']` (e.g. fireworks hit stamps) and `unfreeze()` restores them;
  `check()` reports `lit_n` / `lit_within_tol` (pixels whose expected luma > 0.02: sparse looks) and takes `pts`.

| Module | Kind | What | Audio (Audiogain) | Beat | Est. ms |
|---|---|---|---|---|---|
| fireworks | gen, PAL, HITS 8 | SX-15 / 7C-10: 8 shell slots x <= 128 sparks, analytic (no state). Slot = youngest of hit stamp / Auto (Rate shells/s, **off** by default, U7) / Beatlaunch (one shell per rack beat step). Types peony (Fibonacci sphere), ring (tilted ellipse), willow (drag x2.5, gravity x1.6, life x1.6, trail x3), crossette (Sparks/4 parents split in 4 at Split x life), mixed. Rocket rise, flash, compact smoke glow, capsule sparks (Trail s) with w^2/(d^2 + w^2) cut at 16 w, twinkle. Hitchop default `/project1/lab/AC_audio/out_ctl` channel `kick`. Default Blend add. | burst size | ENV -> brightness; Beatlaunch | 0.8-1.4 |
| bokeh | gen, PAL | SX-22: <= 6 depth layers of out-of-focus discs on hashed cell grids (3x3 neighbours per layer); near = bigger, brighter, faster (parallax); aperture circle / pentagon / hexagon / octagon (Bladerot); edge soft = Softness + Defocus x abs(depth - Focus); Rim onion-ring edge; twinkle; drift direction + layer sway; vertical palette gradient behind | brightness + size | ENV -> brightness | 0.3-0.5 |
| beams | gen, PAL | TC-32 / 7C-20: <= 32 beams; modes fans (two mirrored floor groups: Fan, Tilt, Sweep), cones (row of moving heads, per-beam tilt targets), tunnel (radial laser spokes, Rotspeedb), waves (laser sheets); style beam (soft cone, Beamspread) / laser (core + glow); beat steps re-arrange (tilt / fan / per-beam targets hashed per step, eased over Morph s); fbm haze rising in the beams; source flares; beam i -> palette k (i + 0.5) / Count. Painted trails = chain a feedback module after it (stateless here) | brightness | ENV -> brightness; steps re-arrange | 0.5-1.2 |
| moltenchrome | gen, PAL | TC-23: height = iterated sine domain warp (Iter, Warp, Flow; Surge swells the warp), normals by forward differences (3 heights), view ray reflected into a studio env: Floor / Sky gradient, Lights soft strips sliding (Lightspeed), sharp spec sun (Shine, Spec), Fresnel rim; k = reflected ray height (Colour A -> B duo silver by default; gold duo, shared palette neon). Space page Scale = blob size | warp | ENV -> warp kick | 0.4-0.8 |
| caustic | gen, PAL | SX-04, clean-room (U8): tileable (1 tile = 1 pattern unit, Scale = tiles per screen height). refract = physical caustic density 1 / (abs(det(I + Depth Hess h)) + Soft) - Base of a moving water height (Waves sines, integer wave vectors <= Freq, dispersion sqrt(k)); cells = two layers of animated Worley F2 - F1 edges (Cells, Width). Default Blend add (overlay), duo cyan -> white | Depth (refract) / brightness (cells) | ENV -> brightness | 0.3-0.5 |

### LIVE CHECKS (lane A modules; per module after the A-G steps above)
- **FW1 add + compile:** `add(C, 'fireworks')`; td_errors clean on fx and the module (no `uPal` / `uPalCtl`
  unassigned warning); `pal` CHOP 16 samples, channels r g b pos; `fx` array block 0 = uPal from `pal`.
- **FW2 parity:** preset k, `freeze(I)` (t 2, CHECK hit stamps), next exec `check(I, n=3000)` -> **within_tol >= 0.97
  and lit_within_tol >= 0.95** (lit_n > 50); `stats(I)` = table below (+-0.01).
- **FW3 burst count per Hit = 1:** unfreeze, Clear, pulse `Hit` once -> Hit0 = now, Hitnext 1, `fw_shells` on the read
  uniforms = 1; three more pulses -> 4. Hitchop = a Constant CHOP `kick` 0 -> 1 -> exactly one more shell.
- **FW4 Auto off by default** (no hits: out1 = background, diff 0); Auto on Rate 2 -> shells appear without hits.
- **FW5 palette stops visible:** preset 3 (neon_trio, steps): saturated pixels = one of the 3 stops; Palshift 1/3 ->
  every colour moves one stop; Paldrive bpm_step changes colour without a recompile (fx compile count flat).
- **BK1 bokeh:** add, td_errors clean; every preset `freeze` (t 1 s) + `check(n=1000)` within_tol >= 0.97, `stats`
  = table; drift: Layers 1, Drift 0.05 up, Sway / Twinkle / Gradient 0: out1 at t + 2 s = out1 at t moved up 192 px
  (offline test `test_layer_drifts_at_drift_speed`); passthrough 0; cost <= 1 ms at preset 1 (estimate 0.3-0.5).
- **BM1 beams:** add, td_errors clean; every preset `freeze` (t 1 s, beats 2.5 = CHECK) + `check(n=1000)` within_tol
  >= 0.97, `stats` = table; beat: preset 5 unfrozen at Bpm 120: the look changes once per beat (uDrv.y +2 per s) and
  settles within Morph; passthrough 0; cost <= 1.5 ms (Count 32 laser worst case recorded).
- **MC1 moltenchrome:** add, td_errors clean; every preset `freeze` + `check(n=1000)` within_tol >= 0.95 (the warp is
  chaotic: float32 vs float64 can move a crease by a pixel; report max + p95), `stats` = table (+-0.02); Bump 0 ->
  constant picture (offline `test_flat_metal_reflects_the_viewer`); passthrough 0; cost <= 1.5 ms (estimate 0.4-0.8).
- **CA1 caustic:** add, td_errors clean; every preset `freeze` + `check(n=1000)` within_tol >= 0.97, `stats` = table;
  tileable (offline `test_tileable`: q and q + integer tiles equal to 1e-6); Depth 0 = constant (offline); over the
  test clip with Blend add: out1 >= in1 everywhere; passthrough 0; cost <= 1 ms.
- **FW6 passthrough** Amount 0 / enabled 0 / mix 0 / Panic = 0; **FW7 cost** preset 1 with the CHECK stamps (5 bursts
  + 2 rockets), pane off: <= 3 ms median.

**Spark culling (why the loop is cheap):** every peony / willow / ring spark sits on a ray from the burst origin cg
(its trail start is off that ray by |gy - gy0|), so a pixel at distance rho can only be reached by sparks whose ray
angle is within asin(cut / rho), cut = 16 w + |gy - gy0| (the glow cut). Sparks are angle-sorted (peony: index
jittered +-0.4 of a slot, depth z from a golden-ratio sequence = a projected sphere; ring: the ellipse parameter is
inverted, window / cos(tilt)), so the shader loops only that index window (`gen_pattern_logic.fw_window`; offline
test `test_window_is_conservative`: 0 reaching sparks outside it in 6000 random cases). Crossette skips a parent's 4
children when the pixel is farther than 0.35 R + cut from its split point; a shell is skipped when the pixel is
farther than 1.4 R + 16 w from the segment centre .. centre + gravity drop (flash cut at 8 Rf, glow compact).

Expected numbers (fireworks: frozen t = 2 s, CHECK hit stamps 0.2 0.5 0.8 1.05 1.25 1.7 1.9, Bpm 0, black, Blend add;
regenerate with the test file's `U_for(..., extra=check_pars(m))` + `expect()` after any change):
| Module | Preset | Mean rgb | Lit | Named pixels |
|---|---|---|---|---|
| fireworks | 1 finale mix | 0.040 0.069 0.026 | 0.039 | 123,135,0 / 0,0,0 / 0,1,1 |
| fireworks | 2 gold willow | 0.077 0.018 0.000 | 0.001 | 11,2,0 / 1,0,0 / 0,0,0 |
| fireworks | 3 neon rings | 0.013 0.042 0.030 | 0.022 | 0,7,7 / 0,0,0 / 0,0,0 |
| fireworks | 4 crossette crackle | 0.023 0.019 0.023 | 0.006 | 22,3,15 / 0,0,0 / 0,0,0 |
| fireworks | 5 beat barrage | 0.025 0.011 0.040 | 0.003 | 4,1,3 / 0,0,0 / 0,0,0 |
| bokeh (t 1 s, beats 0) | 1 calm drift | 0.174 0.118 0.326 | 0.030 | 16,0,34 / 95,41,202 / 22,4,23 |
| bokeh | 2 warm hexes | 0.209 0.093 0.022 | 0.022 | 20,5,0 / 133,69,0 / 33,4,0 |
| bokeh | 3 deep focus | 0.110 0.215 0.186 | 0.061 | 0,34,34 / 46,34,0 / 26,2,27 |
| bokeh | 4 rain of light | 0.080 0.172 0.151 | 0.068 | 0,9,10 / 0,169,180 / 0,195,208 |
| bokeh | 5 beat glow | 0.246 0.092 0.249 | 0.034 | 255,151,231 / 8,1,10 / 27,11,23 |
| beams (t 1 s, beats 2.5, Bpm 0 = step settled) | 1 floor fans | 0.050 0.038 0.108 | 0.007 | 0,0,1 / 0,0,0 / 10,19,28 |
| beams | 2 moving heads | 0.150 0.076 0.018 | 0.037 | 3,1,0 / 6,1,0 / 1,0,0 |
| beams | 3 laser tunnel | 0.016 0.025 0.023 | 0.006 | 57,255,20 / 0,0,0 / 1,0,0 |
| beams | 4 laser sheets | 0.012 0.027 0.025 | 0.011 | 0,9,10 / 1,0,1 / 0,1,0 |
| beams | 5 beat fans | 0.050 0.024 0.024 | 0.007 | 8,7,0 / 0,0,0 / 23,0,15 |
| moltenchrome (t 1 s) | 1 liquid silver | 0.421 0.430 0.449 | 0.313 | 105,107,111 / 203,207,217 / 21,21,21 |
| moltenchrome | 2 molten gold | 0.490 0.401 0.198 | 0.234 | 116,94,46 / 174,140,68 / 127,103,50 |
| moltenchrome | 3 surge | 0.486 0.497 0.520 | 0.415 | 183,186,192 / 62,64,66 / 201,206,215 |
| moltenchrome | 4 neon mercury | 0.302 0.097 0.578 | 0.016 | 122,0,255 / 51,7,97 / 2,19,22 |
| moltenchrome | 5 beat ripple | 0.507 0.519 0.542 | 0.500 | 212,216,224 / 93,96,103 / 128,131,139 |
| caustic (t 1 s) | 1 pool light | 0.125 0.238 0.315 | 0.200 | 0,0,0 / 23,62,90 / 9,27,40 |
| caustic | 2 deep focus | 0.087 0.162 0.214 | 0.143 | 0,0,0 / 134,198,236 / 0,0,0 |
| caustic | 3 water net | 0.044 0.110 0.157 | 0.027 | 13,39,58 / 14,39,58 / 1,5,7 |
| caustic | 4 sunlit shallows | 0.134 0.149 0.124 | 0.145 | 0,2,2 / 0,0,0 / 0,0,0 |
| caustic | 5 beat ripple | 0.206 0.355 0.453 | 0.377 | 0,0,0 / 56,123,170 / 59,128,176 |

### Verified live, lane A (27 Oct, 2025.31550, b3; main after the bring-home)
b3's GEN_pattern (3359 ops, same as main's) was the host; rack Input black, other slots enabled 0, pane off for costs.
- **fireworks** (`fireworks1`): FW1 td_errors clean on fx (only a b3 warning: no `AC_audio` there), `pal` 16 samples r g b
  pos, array block 0 = uPal. FW2 every preset: `check(n=2000-3000)` within_tol **1.0**, lit_n 420-876, lit_within_tol
  **1.0**, max 0.002-0.003; `stats` = the table (all means within 0.001). FW3 Hit pulse -> Hit0 = module time,
  Hitnext 1, 1 shell; 3 more pulses -> Hitnext 4; a Constant CHOP `kick` 0 -> 1 on Hitchop -> exactly one more hit.
  FW4 no hits, Auto off: out1 = in1 (max diff 0); Auto on Rate 2 -> 5 shells. FW5 preset 3 Palshift 2/3 + Paldrive
  bpm_step: parity 1.0, `pal` CHOP +0 cooks (only uPalCtl moves). FW6 Amount 0 / enabled 0 / mix 0 / Panic: **0**.
  FW7 cost (preset 1 + CHECK stamps = 5 bursts + 2 rockets): first version **20.0 ms** fx GPU -> angle-window culling
  (T-172) **2.3-2.8 ms p10, 2.8-5.6 ms median** under the shared-GPU load (truchet 1.0 ms in the same minute = its
  26 Oct number); Shells 6 / Sparks 48: 2.3-2.5 p10. Capture
  `output/project1_lab_GEN_pattern_fireworks1_out1_2026-10-26T21-43-26-264Z.png`.
- **bokeh** (`bokeh1`): td_errors clean, 15 vec blocks; every preset check within_tol **1.0** (max 0.002), stats = table.
  Drift: Layers 1, Drift 0.05 up, Sway / Twinkle / Gradient 0, frozen t 1 vs t 3: out1 rows y vs y + 192 max diff
  **1/255** (unshifted mean diff 0.09). Passthrough Amount 0 / enabled 0 / mix 0 / Panic **0**. Cost: first version
  (3 lowbias32 per hash x ~8 hashes x 36 cells) fx GPU median 4.45 ms; one lowbias32 per cell (params from its bytes)
  + a no-hash box reject per neighbour cell + lit radius bound r (not 1.25 r) -> median 3.1 / p10 1.3 alone under
  load. **Paired in the same frames (T-145 method, 140 frames): truchet1 0.41, bokeh1 1.03, fireworks1 2.87 ms fx GPU
  median** (truchet's quiet total is 1.16 ms, PERF_QUIET_27OCT).
- **beams** (`beams1`): td_errors clean; every preset check within_tol **1.0** (lit_within_tol 1.0, max 0.002), stats =
  table (computed with Bpm 0 like `freeze`: the beat age is then 30 s, i.e. the step look settled). Beat drive (preset
  5, Bpm 120, pane on): uDrv.y 2 -> 5 in 1.27 s (one re-arrange per beat). Passthrough Amount 0 **0**. Cost paired
  with truchet in the same frames: preset 1 (12 soft beams) **2.08-2.17 ms** fx GPU (truchet 0.33-0.41), preset 3
  laser tunnel 24 spokes **1.90**, tunnel x 32 lasers 2.58 (estimate 0.5-1.2 was low: ~25 flops + 3 transcendentals per
  beam per pixel; fbm haze only where a beam is and a 4-sigma cut on soft beams changed < 5 %).
- **moltenchrome** (`moltenchrome1`): td_errors clean; every preset check within_tol **1.0** (max 0.0024-0.0035,
  median 0.0015: float32 vs float64 through the 5-step warp stays under 1 level), stats = table (all within 0.0005).
  Passthrough Amount 0 **0**. Cost paired with truchet: **1.22 ms** fx GPU (truchet 0.39). Capture
  `output/project1_lab_GEN_pattern_moltenchrome1_out1_2026-10-26T22-01-56-871Z.png`.
- **caustic** (`caustic1`): td_errors clean; every preset check within_tol **1.0** (max 0.002), stats = table. Over the
  test clip (playing 1.5 s then paused: in1 mean 0.47, std 0.23, T-157 (3)) with Blend add: out1 - in1 min **0**
  (never darker), parity 1.0. Passthrough Amount 0 **0**. Cost paired with truchet: refract **0.74 ms**, cells
  **0.86 ms** fx GPU (truchet 0.20-0.26).
- **Brought home (main, by builder, 22:06-22:08 UTC):** lane registered, GEN_pattern un-parked, `add(C, m, enabled=0)`
  one module per exec (fireworks, bokeh, beams, moltenchrome, caustic: 7 wires each, td_errors 0 on every new
  instance); re-check in main: fireworks preset 1 check within_tol 1.0 (lit 626, over main's truchet1 slot input),
  moltenchrome preset 1 within_tol 1.0 + stats = table; unfrozen, parked, **main saved `JazibTD_home.584.toe`**
  (GEN_pattern 4870 ops, 17 slots, the 5 new ones enabled 0). b3's own rack was the host (same 3359 ops as main, so
  no tox was moved: T-152).

## Rack menu refresh (27 Oct 2026, render-cost lane, T-190 / T-198)
- `_pars` refreshes an existing menu par whose names / labels grew in the spec (`_refresh_menu`, value kept when still a
  valid name), so a rebuild reaches instances built before the menu grew (GEN_pattern, GEN_sdf, GEN_sim racks).
  Offline test `MenuRefresh`. Main: no grown menu found (69 menu pars equal to the spec), so nothing was rebuilt there.
- Rack note (docs/builds/RENDER_COST.md "Cook triggers"): with the pane on a rack, each `<slot>_mix` viewer pulls its
  module even when the slot Switch bypasses it; GEN_points fixed it in its module `out_sel`; GEN_pattern modules
  still cook when shown that way.

## Not done / open
- No per-module cook-ms readout; no Quality par (add only if a module measures > 3 ms).
- columns: heights cannot yet come from a spectrum CHOP (a texture-buffer array, T-110 debug-skin (1), waits for a
  user request); barcode has no text / hex-glyph mode (FX5 G21, needs a glyph atlas).
- truchet multi-scale arc regions are 2-coloured per level only (Carlson's winged tiles not built).
- FX5 G16 Poincare {p,q} hyperbolic tilings and a feedback infinite zoom are not built (one-pass set only).
- gyroid Twist makes the contour width approximate (the gradient ignores the twist term).

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.742).
