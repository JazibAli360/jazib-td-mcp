# fx_film: FX_film rack + 14 modules (film, lens, camera, dof, gate, colour), live in main, 26-27 Oct 2026

`/project1/lab/FX_film`. The film / lens / colour COMP from `docs/research/FX0_effects_backlog.md` (rows 26-32,
FX3 F1-F4, F7, L1-L5, S4). **Status: LIVE on 31550** (built module by module on build TD b2, brought home into the
main .toe, parked, saved): all 10 wave A/B modules pass their LIVE CHECKS ("Verified live" below); wave C (camera,
dof, gate, colour) live on b4 and brought home 26 Oct ("Verified live (wave C)"; polish 27 Oct: dof highlight sprites pass DF3 polygon, camera Trail fused pass). Target ms in the module table
are the prep's targets; measured costs are in "Verified live". The rack is the lean `FX_glitch` rack (template
`docs/builds/fx_glitch.md`), copied, not abstracted.

In: `in1` TOP. Out: `out1` TOP. Rack page: `Panic`, `Input` = auto / live / test clip / **test chart**, `Chart` =
lights (5 discs r 6 px at value `Chartvalue` 4.0 on `Chartbg` 0) / ramp (x ramp 0..1 bottom half, x 0.1 top half) /
grey (`Chartgrey`) / patches (6 x 4 linear patches incl. HDR row). The chart is `rgba16float`, so the chain is 16F
while it is selected (glow energy is not clipped by 8 bits). Positions: `fx_film_logic.LIGHTS`, `PATCHES`.

## Files
| File | What |
|---|---|
| `builders/fx_film.py` | rack (slots / rewire / add / remove / panic), test chart, shared GLSL (`GLSL_LIB`, `EXT`, `PYR`, `MIPG`), helpers `_compute` (expression res, extend, filter, manual dispatch, GLSL Multi TOP for > 3 inputs), `_ext`, `_pyr`, `_outsel`, live-check helpers `solo`, `read`, `logic` |
| `builders/fx_film_<m>.py` | 14 modules: `tonecurve`, `stock`, `halation`, `grain`, `leaks` (wave A); `ca`, `diffusion`, `streak`, `flare`, `star` (wave B); `camera`, `dof`, `gate`, `colour` (wave C) |
| `builders/fx_film_<m>_logic.py` | wave C maths, one file per module (`camera`, `colour`, `gate`, `dof`): mirrors of the GLSL, `.cube` parser + LUT strip + LUT reference (`colour`), `expected_numbers()` |
| `test/test_fx_film_wavec.py` | wave C offline tests (23): maths, dof highlight sprites (excess, tile reach, energy + polygon half-max of a sprite), camera fused acc, colour matrices vs published sRGB -> ACEScg, curve round trips, identity grade, `.cube` 3D / 1D parse + tetrahedral / trilinear reference, apertures, CoC, bokeh polygon, <= 3 GLSL TOP inputs, shared memory <= 32 KB, constant loop bounds, this doc's wave C numbers (the fake-TD build + glslc of the 4 modules run in `test_fx_film.py`) |
| `builders/fx_film_logic.py` | pure maths mirrored by the GLSL + numpy references of the GPU passes (`ext_np`, `glow_np`, `streak_np`, `ca_rgb_expected`) + live-check analysers (`an_*`) + `expected_numbers()` |
| `test/test_fx_film.py` | 36 offline tests (incl. pyramid centroid): rack, templates, presets, a fake-TD run of every `build()` (wiring, uniform set == declared, every expression compiles, every `parent().par.X` exists), glslc compile of all 17 shaders, maths, analysers, this doc's numbers |

## Build / rack edits (td_exec)
```python
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
F = dict(globals()); exec(open(REPO + '/builders/fx_film.py').read(), F)
F['build']('/project1/lab')                          # rack + the 10 rows (ALL enabled 0: cost 0) on first build
F['build']('/project1/<lane>', rows=['halation'])     # a lane's own copy with one row (scratch TD / side TD)
F['add']('/project1/lab/FX_film', 'grain', name='grain1', enabled=0)   # add one row to an existing rack
F['solo']('/project1/lab/FX_film', 'halation1')       # live checks: only this slot on (mix 1)
```
Default order (physical): camera -> dof -> ca -> diffusion -> streak -> flare -> star -> halation -> leaks -> grain ->
gate -> stock -> colour -> tonecurve (the display dither must stay last). A rack built before wave C keeps its `slots`;
add the four rows with orders between the old ones (all enabled 0):
`F['add'](R, 'camera', name='camera1', order=0.5, enabled=0)`, `dof` 0.7, `gate` 8.5, `colour` 9.5.
Offline: `python3 -I -m unittest discover -s test -p 'test_fx_film*.py'` (36 + 23).

## Shared pieces (each used by 2+ modules today; no-bloat rule)
| Piece | Users | What |
|---|---|---|
| `GLSL_LIB` | all 10 | lowbias32 hash (uint32-exact, T-108) / value noise / fbm / luma / sRGB / hue ramp / soft knee (`kneex`, StageLab JZB_Color_Bloom's prefilter) |
| `EXT` pass | halation, diffusion, flare, star | scale x scale box mean (bilinear taps at pixel corners = exact 2x2 means) + soft knee (or the picture, diffusion Mist) into `rgba16float`, edge-held padding to a multiple of 128 / 64 so every mip level is exact (T-116 (1)) |
| `PYR` | halation, diffusion | pyr1..pyr7: 7 small compute ops, each `[1 3 3 1]` / 8 per axis of the level before (4 bilinear taps), edge held: the glow stays centred on the light (TD's box mips put it 8-19 px off, T-129); 0.33 ms GPU for all 7 |
| `MIPG` | halation, diffusion | 4-tap tent at pyramid level k (EXT = level 0, pyr1..7; gather op = GLSL Multi TOP, 9 inputs) + gaussian weight over LEVELS (centre log2(Radius / scale)), levels under weight 1e-3 skipped: one gather instead of a blur chain; the stock Bloom TOP is ~1.7 ms at any size (T-113 (5)) |
| `out_sel` | the 5 multi-pass modules | Amount 0 -> `in1`, the extract/engine is not pulled |
| test chart | every live check | lights / ramp / grey / patches, numbers from `fx_film_logic` |

## Modules (pars: the builder files; presets 4-5 per module, zkit panel)
| Module | Passes | Look | Main pars | Target ms |
|---|---|---|---|---|
| `tonecurve` | 1 | filmic tone curve + **display dither (a mode of the grade, Display page)** | Inspace, Exposure, Curve (ACES fit / ACES Hill / Hable / Reinhard ext / Lottes), Curvemode, Contrast+Pivot, Saturation, Hdesat; Display: Outspace, Softclip, Dither (Bayer 8 / IGN / white / TPDF), Bits, Ditheramp, Ditheranim | 0.15-0.3 |
| `stock` | 1 | stock engine: print / bleach bypass / cross process / two-strip / three-strip Technicolor / B&W | Process, Slope + Offset per channel, Toe, Shoulder, White, Sat shadow/mid/high, Shadow/Highlight tint, Tintbalance, Fade; Process page: Bleach, Cross, Dye, Techamount, Bwfilter, crosstalk rows | 0.2-0.4 |
| `halation` | ext + pyr1..7 + fx | red-orange glow around lights | Intensity, Threshold, Knee, Kneeby, Radius, Spread, Ratio R/G/B 1.4/1.0/0.7, Tint, Source, Blend, Core, Quality | 0.5-0.9 |
| `grain` | 1 | 3 models: hash / noise 3D (evolving) / clumped | Strength (std dev), Model, Size, Clump, Chroma, Shadow/Mid/High response, Blend, Animate (frame / hold at Grain fps / frozen), Evolve, Lattice2, Seed | 0.2-0.6 |
| `leaks` | 1 | light leaks + film burn | Mode, Intensity, Blend, Edge, Position, Size, Softness, Blobs, Drift, Speed, Warp, Noisescale, 3 colours, Freeze/Phase; Burn: Level, Burnwidth, Charwidth, origin; Trigger: Envmode, Breathe, Trigger pulse, Attack/Hold/Release | 0.3-0.5 |
| `ca` | 1 | physical lateral CA, Cauchy dispersion, spectral N taps, longitudinal blur, purple fringe | Mode, Lateral K1 / K2 (px at the half-diagonal), Curve, Taps, Longitudinal, Fringe, centre, anisotropy | 0.2-0.8 |
| `diffusion` | ext + pyr1..7 + fx | Bloom / Mist (Pro-Mist, Black Mist) / Glimmer on ONE pyramid | Mode, Intensity, Threshold, Knee, Radius, Spread, Soften, Veil, Tint, Glimmer pars, Quality | 0.5-0.9 |
| `streak` | ext + run + fx | anamorphic streak at any Angle (rotated frame, exact exponential row sum) | Intensity, Threshold, Knee, Length, Corelength, Coregain, Angle, Tint, Coretint, Sourcecolor, Along, Thickness | 0.4-0.8 |
| `flare` | ext + flare + fx | pseudo lens flare (Chapman): ghosts, halo, CA, dirt, starburst | Ghosts, Dispersal, Ghostfalloff, Ghostblur, Ghosthue/sat, Distortion, Halo width/gain/falloff, optical centre, Dirt, Burst, Blades, Quality | 0.4-0.8 |
| `star` | ext + star + fx | cross-screen / star filter spikes | Points, Length, Falloff, Rotation, Spin, Taper, Taps, Rainbow, Hue, Tint, Quality | 0.6-1.2 |
| `camera` (C) | path + ae + geo (Trail off) / acc (Trail on: geo fused with the trail) + fx | camera body: handheld move (1/f shake, footsteps free / Bpm, wobble, pan, zoom), rolling shutter (per-row time: skew / jello of the move, Pan), shutter blur of the move (Samples taps inside Shutter angle at Fpsbasis), content trail (same mean age as the shutter), exposure + auto exposure (lag), mains flicker bands (sinc over the shutter), flash banding (Trigger pulse / every Flashbeats beats), ISO noise (Poisson-Gaussian, chroma, fixed pattern, hot pixels) | Camera: Inspace, Shutter, Fpsbasis, Moveblur, Samples, Trail, Edge, Overscan, Freeze/Phase/Speed; Handheld; Rolling; Exposure | 0.4-1.0 |
| `dof` (C) | af + coc + hl + gather + fx | depth of field: depth from Depthtop, else DC_depth_cam (auto), else a focus plane / radial / luma; Gustafsson-style gather on a Vogel spiral + highlight sprites (excess over Spritethr drawn as the aperture shape per tile, Sprites share); disc / polygon, squeeze, cat's eye, swirl, rim, highlight boost; AF point / Bpm rack / Racktime | Focus page (Depthsource, Focus, Range, Fstop, Maxblur, Nearscale, Nearreach, plane), Bokeh, Rack | 0.8-1.5 |
| `gate` (C) | 1 | gate / format overlays (aspect apertures, mask / fit / fill, rotate inside, rounded soft gate, jitter), film strip (frames, frame lines, 4-perf / 2-perf / super 8 / 16 mm sprockets, edge marks, scroll free / Bpm), vintage lens (distortion, cos^4 vignette + oval + cast, mechanical vignette, soft corners, Petzval swirl, spherical glow, microcontrast) | Gate, Strip, Lens pages | 0.1-0.5 |
| `colour` (C) | 1 (+ 2 Script TOPs) | ACES-style pipeline: in space (sRGB / Rec.709 / linear / ACEScg / LogC3 / S-Log3 / ACEScct) -> ACEScg -> exposure, WB, ASC CDL, lift/gamma/gain, contrast, sat / vibrance (linear or ACEScct) -> LUT A/B (.cube 3D / 1D, tetrahedral / trilinear, morph, mix) -> view: encode Outspace (LogC3 = log view) or ACES SDR (Hill) -> sRGB; gamut clip; split wipe | Grade, Wheels, LUT, View pages | 0.2-0.4 |

Design notes the live lane should know:
- Every pass is compute GLSL (T-46/T-47); resolutions are expressions on `op('in1')`; output-size checks use
  `uTDOutputInfo.res.zw` (as motion_trail / projector_dome, live on 31550).
- `streak` `run`: `local_size_x 64`, manual dispatch `1 x rows` (T-114 (1) pars), 8 elements per thread in registers,
  only 2 x 64 vec4 shared (2 KB). A first draft kept 5 x 512 vec4 in shared memory (43 KB): over the 32 KB per workgroup
  Apple GPUs allow (FX6 1c used exactly 32 KB) - caught offline, the test now asserts <= 32 KB.
- `ca` switches `inputfiltertype` to mipmap only while Longitudinal or Fringe > 0 (textureLod reads level 0 otherwise).
- `grain` noise 3D normalises by its z factor at fract(z), so Evolve 1 (integer z) keeps the same std dev.
- No flash / luminance caps anywhere (user rule 26 Oct); FX3's "Safe cap" proposals are dropped.
- Wave C state passes (`camera/ae`, `camera/acc`, `dof/af`) are in-place compute (`readwrite`, `clearoutputs` off,
  rgba32float) stamped with `absTime.frame % 2048`: a second cook in the same frame recomputes from the stored
  `before` (ae / af) or keeps the stored result (acc, one buffer since the 27 Oct polish; no double step); a gap of g frames steps by the real time (acc: weight a^g; ae / af: dt = g / cookRate),
  a gap > 30 frames restarts from the input (module was bypassed; T-156 (1): under load TD skips 1-4 frames per
  cook). No Feedback TOPs.
- `camera/path` is 257 x 1 (texel 128 = now, exact): the move is evaluated once per frame on a +-Wh s window and every
  row / shutter tap interpolates it (rolling + blur cost no per-pixel noise).
- `colour` LUTs: the Script TOPs parse the `.cube` in Python (cached in `scriptOp.storage` by path + mtime + size;
  Reload pulse; never fetch/store inside its own cook, T-156 (2)) into an
  rgba32float strip (N*N x N + a header row: DOMAIN_MIN / MAX, N, valid); the shader reads it with texelFetch (8
  fetches trilinear, 4 tetrahedral: exact, no 32F filtering needed). 1D LUTs become a 33^3 cube. No OCIO TOP: FX6 has
  no `.cube` probe result, and the own route is exact and testable (OCIO TOP stays a free option, not probed here).
- `dof` reads `/project1/lab/DC_depth_cam/depth` (R = nearness) when Depthsource is auto and no Depthtop is set;
  without it the procedural plane is used (a person-mask / depth TOP can be set any time).

## LIVE CHECKS (per module ~15 min; checks match the risk)
Common steps for each module `<m>` (instance `<m>1`). Measure in separate execs: set pars in one, read >= 3 frames
later in the next (T-111 (4), T-116 (4)). `R` = the FX_film COMP.
1. **Register + build** (2 min): `python3 tools/lane.py add FX_film "<label>"`; `R.allowCooking = True`; build or
   `add` the row; `td_errors` on `R/<m>1` clean (GLSL compile: `td_trace` / errors on `fx`, `ext`, `run`, `flare`,
   `star`); `td_layout` flow on the instance.
2. **Passthrough** (2 min): `F['solo'](R.path, '<m>1')`, `R.par.Input = 'test'`, clip paused; Amount 0 -> `an_diff`
   (img_src, out1) max **0**; Amount 1 + slots.enabled 0 -> max 0; Panic on -> max 0.
3. **Numbers** (5 min): the module's check below, `R.par.Input = 'chart'`.
4. **Cost** (3 min): `td_perf` on the instance, 120 pulled frames, median ms (sum of the instance's TOPs, chart /
   clip excluded) <= the target above, and the project's real fps (td_watch, 300 frames, pane off the COMP, others
   parked) 60; report both.
5. **Capture + save** (3 min): one preset on the test clip, `td_screenshot` of `R/<m>1/out1`; `td_checkpoint`;
   fill "Verified live" below; when done park `R` and `python3 tools/lane.py remove FX_film`.

Read snippet (exec B): `L = F['logic'](); a = R.op('img_src').numpyArray(delayed=False);
b = R.op('out1').numpyArray(delayed=False)`; analysers take these arrays (row 0 = bottom, x right).

### Expected numbers (`fx_film_logic.expected_numbers()`, asserted by the offline test)
```
tc_aces_fit_018 0.2669
tc_aces_fit_1 0.8038
tc_hable_018 0.0671
tc_reinhard_1 0.5312
tc_lottes_018 0.18
tc_hill_018 0.1056
dither_tile_mean_lsb 127.5
dither_frac_up 32
dither_4bit_levels [7, 8]
stock_018 0.18
stock_1 0.9329
stock_009 0.0733
bleach_r_of_06_03_02 0.4279
tech2_red [1.0, 0.42, 0.16]
tech3_red [0.705, 0.27, 0.125]
ext_sum_half 1728.0
ext_sum_quarter 1472.0
hal_w_r [0.0, 0.0, 0.008, 0.078, 0.289, 0.393, 0.196, 0.036]
hal_w_b [0.0, 0.008, 0.078, 0.288, 0.392, 0.196, 0.036, 0.002]
hal_energy [1726.9, 518.3, 103.7]
hal_r_at_570_960 0.0292
hal_r_at_600_960 0.0054
hal_gq_half_energy_r 1726.9
hal_gq_half_r_at_570_960 0.0289
hal_gq_half_peak_ratio 0.957
bloom_energy_r 1720.9
bloom_r_at_580_960 0.0112
streak_at_640_960 0.06777
streak_at_740_960 0.04856
streak_at_640_972 0.0
grain_sigma_05 0.75
grain_std_amount01 0.075
vn_norm2 4.66321
grain_corr_05 0.683
burn_frac 0.618
env_mid_release 0.5
ca_corner_px 11.99
ca_blue_factor -2.328
streak_dims_0 [135, 960, 8.0]
streak_dims_90 [240, 540, 8.0]
streak_dims_30 [237, 1102, 8.0]
streak_ratio_100_200 0.7165
flare_ghosts [(0, 0, 432, 1152), (0, 1, 403, 1204), (0, 2, 306, 1376), (0, 4, 621, 816), (0, 5, 558, 928), (1, 0, 772, 1812), (1, 5, 105, 48), (2, 0, 92, 512), (2, 5, 1011, 1781), (3, 0, 772, 512), (3, 1, 926, 219), (3, 5, 105, 1781), (4, 0, 92, 1812), (4, 5, 1011, 48)]
star_angles_6_15 [15.0, 75.0, 135.0, 195.0, 255.0, 315.0]
```
Chart values pass through `rgba16float` (0.18 is stored as 0.17993): compare curve outputs with 2e-3 tolerance.

### Wave C expected numbers (`fx_film_<m>_logic.expected_numbers()`, asserted by `test_fx_film_wavec.py`)
```
cam_shutter_frames_180_24 1.25
cam_trail_a_360_24 0.4286
cam_trail_a_720_24 0.6667
cam_trail_step3_720 0.7037
cam_pan_top -12.493
cam_pan_bottom 12.493
cam_flicker_sinc_180_24 0.0395
cam_flicker_sinc_1_100 0.0
cam_flash_rows_45 240
cam_iso_sigma_018_3200 0.08
cam_iso_sigma_05_800 0.04308
cam_ae_ev_009 1.0
col_srgb_to_ap1_r [0.613097, 0.339523, 0.047379]
col_logc3_018 0.391
col_slog3_018 0.4106
col_acescct_018 0.4136
col_logview_018 0.391
col_aces_view_018 0.3585
col_exp1_018 0.36
col_cdl_slope2_offs 0.3558
col_lgg_lift01_gain12 0.66
col_wb_warm1 [0.2305, 0.1686, 0.1401]
gate_rows_239 452
gate_rows_185 584
gate_cols_239_rot 803
gate_vig_corner_k1 0.25
gate_vig_mid_k1 0.7901
gate_strip_cell_3 [640.0, 410.4, 313.0]
dof_coc_row_960 0.0
dof_coc_row_1400 9.812
dof_coc_row_1800 19.812
dof_coc_row_200 -17.787
dof_poly_edge_6 0.866
dof_flat_coc_f14 30.0
dof_sprite_tile_15 8
dof_aperture_area_6 2.5981
```

### tonecurve (wave A)
- **TC1 curves:** Chart grey, Chartgrey 0.18 then 1.0; Inspace linear, Outspace same, Dither off, Exposure 0,
  Contrast 1, Saturation 1, Hdesat 0. Read `out1` centre pixel r: Curve aces_fit -> `tc_aces_fit_018` / `tc_aces_fit_1`;
  hable (Whitepoint 11.2) -> `tc_hable_018`; reinhard (Whitepoint 4, grey 1.0) -> `tc_reinhard_1`; lottes (Lcontrast
  1.6, Shoulder 0.977, Whitepoint 8) -> `tc_lottes_018` (mid grey is a fixed point); aces_hill -> `tc_hill_018`.
  r = g = b for every curve on grey (+-2e-3).
- **TC2 display dither:** Chartgrey 0.5 (exact in 16F), Curve off, Dither bayer8, Bits 8, Ditheramp 1: every value
  127/255 or 128/255 (`an_levels(b, 0, 0, 1080, 1920, bits=8)` < 0.125 LSB: compute stores into 16F truncate, one 16F
  step on [0.5, 1) is 0.1245 LSB, T-129 (4)), `an_tile_means` of any
  8x8 tile x 255 = `dither_tile_mean_lsb` (= `dither_frac_up` of 64 px at 128); Bits 4: values in
  `dither_4bit_levels` / 15 only. Chart ramp + IGN / white / TPDF: `an_levels` < 0.125 LSB and the 64 px row mean
  within 0.5 LSB of the ramp mean. Ditheranim on: two reads 5 frames apart differ (pattern moves), off: identical.

### stock (wave A)
- **ST1 neutral curve:** Chart grey, Inspace linear, Process print, every other par default: Chartgrey 0.18 ->
  `stock_018` (fixed point), 0.09 -> `stock_009`, 1.0 -> `stock_1`; r = g = b (+-2e-3).
- **ST2 processes keep neutrals neutral:** grey 1.0 with Process tech2 (Dye default), tech3, bw: r = g = b = `stock_1`
  (+-2e-3). Bleach on grey: r = g = b. Patches chart, Process tech3: the saturated row (row 1) gains saturation
  (max - min of each patch rises) and every grey patch (row 0) is unchanged vs Process print (diff < 2e-3).
- Maths spot values for the doc of the look: `bleach_r_of_06_03_02`, `tech2_red`, `tech3_red` (display-space
  operators before / after the curve, `fx_film_logic.bleach / tech2 / tech3`).

### halation (wave A)
- **HA1 energy + profile:** Chart lights (value 4), Threshold 0.8, Knee 0.2, Kneeby max, Radius 20, Spread 1,
  Tint (1, 0.3, 0.06), Source luma, Blend add, Core 0, Intensity 1, Quality half. `an_added_energy(b, a)` =
  `hal_energy` per channel (+-5 %; = Intensity x tint x `ext_sum_half`: mip gather conserves energy). Added red
  (`b - a`, channel 0) at (570, 960) = `hal_r_at_570_960`, at (600, 960) = `hal_r_at_600_960` (+-10 %). Default
  Radius 40 level weights: `hal_w_r` (red, 56 px) / `hal_w_b` (blue, 28 px): red reaches one level further.
- **HA2:** Core 1 -> added energy drops (the halo sits around the disc); Blend screen on the clip: no channel goes
  above max(in, 1) where in <= 1.

### grain (wave A)
- **GR1 std dev:** Chart grey 0.5, Strength 0.1, Amount 1, Shadow 0.6 / Mid 1 / High 0.4, Blend add, Chroma 0:
  `an_stats(b)` std = `grain_std_amount01` (+-4 %) for EACH Model (hash Size 1 and 2, noise3d Size 2 Evolve 1 and
  0.37, clumped Size 1.5 Clump 0.5), mean 0.5 +-0.002, `corr_rg` 1.0. Lattice2 on: same std (+-4 %).
- **GR2 colour:** Chroma 0.5 -> `corr_rg` = `grain_corr_05` (+-0.03), std unchanged (+-4 %).
- **GR3 timing:** Animate hold, Grainfps 24: two reads 1 frame apart are identical in >= ~50 % of attempts at 60 fps
  (24 on 60), frame mode: never identical; frozen: always identical. Response ends: grey 0 with Shadow 0 -> std 0;
  grey 1 with High 0 -> std 0 (sigma(0) = Shadow, sigma(1) = High: set Shadow 0 to keep LED black clean).

### leaks (wave A)
- **LK1 leak:** Mode leak, Freeze on, Phase 0, Envmode continuous, Breathe 0, Level 1, Blend screen on the clip:
  out >= in everywhere (screen only adds); Level 0 -> diff 0.
- **LK2 burn:** Chart grey 0.5, Mode burn, Freeze on, Phase 0, Envmode continuous, Breathe 0, Level 0.5,
  Burnwidth 0.06, Warp 0.25, Noisescale 3, Posx 0, Posy 0, Seed 7, Intensity 1: share of pixels sampled every
  20 px (x, y from 10) whose value equals Color1 (white-hot core) = `burn_frac` (+-0.01; same lowbias32 hash).
  `fx_film_logic.burn_fraction` recomputes it for any other setting.
- **LK3 trigger:** Envmode triggered, Attack 0.1, Hold 30, Release 0.8: pulse Trigger -> Hittime = absTime.seconds
  (+-0.1); 1 s later the burned share = `burn_fraction(Level 0.5)` again; `envelope()` at 1.0 s after the pulse with
  Hold 0.5 is `env_mid_release`.

### ca (wave B)
- **CA1 lateral shift:** clip paused, Mode rgb, Lateral 12, Lateral4 0, Curve 1, Longitudinal 0, Fringe 0: at 200
  random pixels `out1` rgb = `L.ca_rgb_expected(a, x, y, 12, 0, 1.0)` (max error < 2/255: GPU bilinear weights).
  Red shift at the top-right corner pixel = `ca_corner_px` px, blue = `ca_blue_factor` x red (opposite side).
  Centre pixel (539, 959): out = in (shift 0).
- **CA2 spectral:** Mode spectral, Taps 8, chart grey: out = in (+-2e-3; weights normalised per channel: white stays
  white). Longitudinal 4 on the lights chart: the disc edge shows a colour fringe (blue widest).

### diffusion (wave B)
- **DF1 bloom energy:** Chart lights, Mode bloom, Threshold 0.8, Knee 0.2, Radius 30, Spread 1.5, Tint (1, 1, 1),
  Intensity 1, Quality half: `an_added_energy` r = `bloom_energy_r` (+-5 %), r = g = b; added red at (580, 960) =
  `bloom_r_at_580_960` (+-10 %).
- **DF2 mist:** Mode mist on the clip, Soften 0.45, Veil 0: mean luma unchanged (+-2 %), std dev of luma drops
  (contrast down); Veil 0.05 lifts the darkest 1 % of pixels. Glimmer: sparkle pixels only where the bloom is > 0.

### streak (wave B; build on the scratch TD first: shared memory + barriers + manual dispatch)
- **SK1 dims:** `ext` / `run` resolution at Angle 0 / 90 / 30 = `streak_dims_0` / `_90` / `_30` (nx, ny, Along);
  `run` dispatch = 1 x ny.
- **SK2 profile:** Chart lights, Angle 0, Length 300, Corelength 40, Coregain 0, Tint (1, 1, 1), Sourcecolor 0,
  Threshold 0.8, Knee 0.2, Along 8, Thickness 2, Intensity 1: added red at (640, 960) = `streak_at_640_960`, at
  (740, 960) = `streak_at_740_960` (+-5 %), ratio = `streak_ratio_100_200` (= exp(-100 / Length), +-2 %); 12 px
  above the row, (640, 972): `streak_at_640_972` (< 1e-4). The scan itself is exact (`scan_chunked == scan_brute`):
  a mismatch here is the GPU side.
- **SK3 angle:** Angle 90: the streak runs along y through each light (profile along 90 deg same ratio).

### flare (wave B)
- **FL1 ghost positions:** Chart lights, Centerx 0.45, Centery 0.55, Ghosts 6, Dispersal 0.35, Ghostfalloff 2,
  Ghostblur 0, Distortion 0, Halogain 0, Dirt 0, Burst 0, Intensity 4, Quality quarter: every (light, ghost, x, y)
  in `flare_ghosts` has an added-luma local max (9 px window) > 0, and >= 90 % of the added energy lies within 24 px
  of one of them. `fx_film_logic.flare_predictions(dispersal, ghosts, centre)` for other settings.
- **FL2:** Halogain 1 adds a ring; Dirt 1 / Burst 1 change the flare's brightness pattern only (no added energy
  where the flare buffer is 0).

### star (wave B)
- **SR1 arms:** Chart lights, Points 6, Rotation 15, Spin 0, Length 220, Falloff 3, Rainbow 0, Intensity 2, Quality
  half: `an_ring_peaks(b, 540, 960, 60, base=a)` returns 6 peaks at `star_angles_6_15` (+-3 deg each); Points 4,
  Rotation 45: 4 peaks at 45 / 135 / 225 / 315.
- **SR2:** peak / median on the ring at radius 90 >= 10 (arms, not a round glow; at radius 60 the lod-blurred core
  overlaps the arms, live 6.2).

### camera (wave C)
- **CM1 neutral:** Inspace linear, defaults (no move, Readout 0, Iso 0, Trail 0, Mains off, Flash off), chart
  patches: out = in (max < 1e-3). Exposure 1 on grey 0.18 -> `col_exp1_018` (0.36).
- **CM2 path = logic:** Freeze on, Phase 3.3, Shake 20, Shakerot 2, Zoomshake 0.05, Steps 6, Stepsroll 1, Wobble 3,
  Panx 300, Readout 1, Moveblur 1: `path` texel i = `path_at((i/256 - 0.5) 2 Wh)` (max < 1e-3 px / rad). Then Moveblur
  0, Readout 0 on the clip: 200 pixels = bilinear(in, `src_point(path_at(0))`) (< 2/255).
- **CM3 rolling pan:** chart ramp, Inspace linear, Readout 1, Fpsbasis 24, Panx 600, Moveblur 0, Edge hold: per bottom
  row, shift = (P.x / W - out) W (columns 100-980): row 0 = `cam_pan_bottom`, slope -600 / 24 / 1920 px per row.
- **CM4 flicker:** grey 0.5, Mains hz50, Banddepth 0.3, Shutter 45, Fpsbasis 24, Readout 1, Freeze, Phase 0: row
  profile out / 0.5 = `flicker_gain(0, 100, row_time, 0.3, T)` (max < 2e-3); Shutter 180 -> amplitude x
  `cam_flicker_sinc_180_24`.
- **CM5 flash band:** same, Mains off, Flashmode trigger, Flashgain 2, Flashwash 0, pulse Flash (Freeze: age 0): rows
  with coverage > 0.5 (out > 0.5 x 2) = `cam_flash_rows_45` (+-3; 332 rows are partly lit), lit rows = 0.5 x 3.
- **CM6 trail:** Shutter 720, Fpsbasis 24 (cookRate 60), Trail 1: uniform a = `cam_trail_a_720_24`; static grey -> out
  = in; for the step use Fpsbasis 2 (a = 59/61, slow enough for exec latency), let grey 0.2 settle >= 6 s, step to 1.0
  and read `acc` (32F, not out1): each read v gives n = log((1 - v) / 0.8) / log(a) integer (+-0.05).
- **CM7 ISO:** grey 0.5 linear, Iso 800, Chroma 0, Fpn 0, Hotpixels 0: std = `cam_iso_sigma_05_800` (+-4 %), mean
  0.5 (+-0.002), corr_rg 1; Chroma 0.5: corr_rg 0.5 (+-0.03), std same.
- **CM8 AE:** grey 0.09 linear, Autoexp on, Aetarget 0.18, 2 s: out 0.18 (+-1 %) (= ev `cam_ae_ev_009`).

### colour (wave C)
- **CO1 identity:** defaults (Inspace srgb, Outspace same, view none, LUTs empty) on the clip and the patches chart:
  out = in (max < 2e-3, 16F / 8-bit rounding only).
- **CO2 spaces + grade:** grey 0.18, Inspace linear: Outspace logc3 -> `col_logview_018`; Viewmode aces ->
  `col_aces_view_018`; Exposure 1 -> `col_exp1_018`; grey 0.1 Sloper 2 Offsetr 0.05 -> r `col_cdl_slope2_offs`;
  grey 0.5 Lift 0.1 Gain 1.2 -> `col_lgg_lift01_gain12`; Temperature 1 -> `col_wb_warm1`. Patches with a mixed grade
  (CDL + LGG + contrast + sat + vibrance, both Gradespaces): every patch = `colour_px` (max < 2e-3).
- **CO3 LUT:** `write_cube` test LUTs (17^3 non-linear, 9^3) into `output/fx_film_wavec/`; `lut_a` numpyArray =
  `cube_strip(parse_cube(file))` exactly (orientation); Lutin linear on the linear patches / ramp chart: out =
  `colour_px(..., lut_a, lut_b)` for tetrahedral and trilinear, Lutmorph 0.5, Lutmix 0.5 (max < 1e-3).

### gate (wave C)
- **GA1 passthrough + apertures:** Aspect off, lens 0: out = in (max 0) on the clip. Grey 1, Aspect 2.39 mask, Gatesoft
  1: centre column rows > 0.5 = `gate_rows_239`; 1.85 -> `gate_rows_185`; 2.39 Rotate fit -> centre row picture
  columns = `gate_cols_239_rot` (+-2).
- **GA2 vignette:** grey 1, Aspect off, Vignette 1, Vigcolour (1, 1, 1): pixel (540, 1440) = `gate_vig_mid_k1`, corner
  ~`gate_vig_corner_k1` (+-1e-2).
- **GA3 strip:** Strip on, Frames 3, Sprockets 4-perf, Scroll 0, Scrollphase 0: frame lines every 640 rows (cell
  `gate_strip_cell_3`), 4 holes per cell in each band (12 per side).

### dof (wave C)
- **DF1 CoC:** Depthsource plane (angle 0, tilt 1), Focus 0.5, Range 0.05, Fstop 2.8, Maxblur 24, Quality half,
  Focusmode manual: `coc` alpha at each texel = `coc_px(plane_depth(texel centre))` (+-0.05 px; `dof_coc_row_*` at
  full-res rows 960 / 1400 / 1800 / 200).
- **DF2 in focus exact:** rows 930-990 (inside the Range zone, beyond the near reach): out = in (max 0).
- **DF3 bokeh:** Planetilt 0, Focus 0, Range 0, Fstop 1.4, Maxblur 30 (`dof_flat_coc_f14`), lights chart: the centre
  light becomes a disc of half-max radius ~30 px (+-4); Shape polygon Blades 6 (Sprites 1, Spritethr 0.8 = defaults): half-max radius at the vertex angles /
  at the edge angles > 1.05 (ideal 1 / `dof_poly_edge_6`, blurred by the 6 px light).
- **DF4 rack:** Focusmode point at (0.5, 0.75) on the plane -> `af` r = 0.75 (+-0.005) after Racktime; Focusmode bpm:
  `af` follows Focus / Focus2 on the beat.

## Lanes (several TDs at once; user 26 Oct: "use multiple tds")
10 modules x ~15 min. Fastest safe plan (~35-40 min wall clock + ~20 min merge): 5 lanes x 2 modules, each lane in
its own TD or under its own parent on the scratch TD (`/project1/<lane>/FX_film`, T-117 (5)), building only its rows
(`build('/project1/<lane>', rows=[...])`): A tonecurve + stock, B halation + diffusion (same EXT/MIPG), C grain +
leaks, D streak (scratch first) + ca, E flare + star. Then ONE merge lane in the main TD (everything ends in the main
.toe): `build('/project1/lab')`, steps 1-2 for all 10, one number check each, combined fps with a typical stack on
(ca + diffusion + halation + grain + stock + tonecurve), save, park. Lanes only change builder files through git
with `git commit -- <paths>` (T-116 (6)).

## Verified live
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
26 Oct 2026, TD 2025.31550. Built module by module in build TD **b2** (`/project1/lab/FX_film`, `streak` first on the
scratch TD), checks run there, then brought home into the **main** TD (`/project1/lab/FX_film`, 3016 ops, errors 0,
layout check ok, parked, `JazibTD_home.368.toe`; one light number per module re-run in main, all equal to b2).
Transfer `output/transfer/FX_film.tox` (Version 1.0.0); b2 checkpoints `output/checkpoints_b2/FX_film/`. Captures
`output/project1_lab_FX_film_<m>1_out1_2026-10-26T*.png` (one preset per module on the test clip; the clip itself has
motion-blurred frames). All passthrough checks (Amount 0, slot disabled, Panic) = max diff **0** for every module.
Load: 4-6 TDs and several lanes busy the whole time (b2 10-33 fps, main 5.7-17.8 fps whatever FX_film did), so
costs are per-op medians (gpu + cpu cook) of the module's own TOPs over 60-120 cooked frames and run high.

| Module | Numbers (live vs expected) | Cost ms (load as above) |
|---|---|---|
| tonecurve | fit 0.18 -> 0.2666 (0.2669), 1 -> 0.8037 (0.8038); hable 0.0671; reinhard 0.5308 (0.5312); lottes 0.1798 (fixed point); hill 0.1055 (0.1056); r = g = b. Bayer 8: values 127 / 128 only, tile mean 127.47 (16F), 4 bit 7 / 8 only; IGN / white / TPDF row means within 0.13 LSB; anim on differs, off identical | fx 0.12-0.24 GPU |
| stock | 0.18 -> 0.1798, 0.09 -> 0.0732 (0.0733), 1 -> 0.9326 (0.9329); tech2 / tech3 / bw on grey 1 = 0.9326, r = g = b; bleach grey neutral; patches tech3: grey row unchanged, saturated row 0.554 -> 0.681 | fx 0.30 |
| halation | energy 1723 / 516 / 102 (1727 / 518 / 104); red at 570 0.0292 (0.0292), 600 0.0054; quarter 1468 (1472); Core 1 drops energy; screen never above max(in, 1); halo centroid 0.1-2 px from every chart light (box mips: 8-19 px, fixed, T-129) | ext 0.33 + pyr1..7 0.33 + fx 1.1 GPU; + ~0.9 CPU |
| grain | std 0.0742-0.0750 (0.075) for hash 1 / 2, noise3d (Evolve 1 / 0.37), clumped, Lattice2; mean 0.4997-0.5001; Chroma 0.5: corr_rg 0.683 (0.683), channel std unchanged; frame never identical, frozen always, hold at 1 fps 11 / 15 identical (b2 too slow for a 24 fps hold test); grey 0 + Shadow 0 and grey 1 + High 0 -> std 0 | fx 1.2 (clumped + Lattice2, heaviest preset) |
| leaks | screen leak: out >= in (min 0), Level 0 diff 0; burn share 0.6186 (0.618); trigger: Hittime = pulse + 0.1 s (one frame), share back to 0.6186 1-2.2 s later | fx 0.7-0.8 |
| ca | 200 px vs `ca_rgb_expected` max 0.53 / 255 (< 2); corner shift 11.99 px; blue -2.328 x red; centre 0; spectral on grey exact (0); longitudinal fringe widest in blue | fx 0.85 (spectral 8 taps + longitudinal + fringe); rgb 0.15 |
| diffusion | bloom energy 1717 r = g = b (1720.9), red at 580 0.0112 (0.0112); mist: mean 0.4766 -> 0.4758, std drops 0.2256 -> 0.2242 (highlights only); Veil 0.05 lifts the darkest 1 % 0.064 -> 0.087; glimmer sparkles only where EXT excess > 0 (0 of 24141 outside) | ext 0.41 + pyr 1.1 + fx 1.29 GPU (heavier load); main stack 2.4 GPU + 1.6 CPU |
| streak | dims 135 x 960 / 240 x 540 / 237 x 1102, dispatch 1 x rows; red at 640 0.06769 (0.06777), 740 0.04852 (0.04856), ratio 0.7169 (0.7165), 12 px above 0.0; Angle 90 same ratio 0.717 | 0.31 GPU + 0.41 CPU total |
| flare | all 14 predicted ghosts found, 94 % of the added energy within 24 px of them; Halogain 1 adds energy; Dirt / Burst only reshape (>= 95 % still at the ghosts) | ext 0.49 + flare 0.10 + fx 0.44 |
| star | 6 points at r 90: 16 / 78 / 136 / 196 / 252 / 311 (15 ... 315, two arm lines ~3 deg off, T-129 (5)); 4 points 45.5 / 135.5 / 226 / 312.5; peak / median 21 at r 90 (6.2 at r 60) | ext 0.48 + star 0.76 + fx 0.12 |

Typical stack in main (ca rgb 2 + diffusion + halation 800T + grain 35mm + stock warm print + tonecurve aces): GPU 5.9
ms, CPU 3.8 ms (diffusion and halation ~2 ms GPU + ~1.5 ms CPU each: the 9-op glow chains); main ran 17.8 fps with the
stack on vs 5.7 fps parked minutes earlier (other lanes' load dominates; no fair 60 fps test possible today).

## Verified live (wave C)
26 Oct 2026, TD 2025.31550, build TD **b4**: main's FX_film (export `output/transfer/FX_film_src.tox`, 3016 ops, 22:36)
loaded into b4 (31 s), the 4 rows added with `F['add']` (camera 0.5, dof 0.7, gate 8.5, colour 9.5, enabled 0),
chain camera -> dof -> ca ... grain -> gate -> stock -> colour -> tonecurve, layout check ok (rack + 4 instances), errors
0. Brought home into **main** with `tools/bring_home.mjs` (4181 ops both sides, errors 0, parked, `JazibTD_home.448.toe`;
b4 `Build4.72.toe`, checkpoint `output/checkpoints_b4/FX_film/`). Passthrough (Amount 0, slot disabled, Panic) = max
diff **0** for all four. Captures `output/project1_lab_FX_film_<m>1_out1_2026-10-26T18-28-*.png` (handheld doc /
hex night / super 8 gate / warm print, stacked). Load: 6 TDs; b4 ran 27 rack cooks/s with every slot off, 22 with the
four wave C modules on (heavy settings) - no fair 60 fps number today.

| Module | Numbers (live vs expected) | Cost ms (one-op sampler, median per op, summed; T-156 (4)) |
|---|---|---|
| camera | CM1 patches out = in (0), Exposure 1: 0.3599 (0.36); CM2 path vs `path_at` max 4e-5 px / 1e-7 rad, 200 clip px vs bilinear(`src_point`) max 0.58 / 255; CM3 row 0 shift 12.46 (12.49; 16F ramp = 0.5 px steps), slope -0.013020 (-0.013021) px/row; CM4 flicker profile max err 1e-3 at 45 and 180 deg, amplitude 0.1829 / 0.0120 (0.1830 / 0.0119); CM5 240 rows cov > 0.5 (240), lit 1.5; CM6 a 0.6667, step n 20.998 / 37.998 / 59.998 / 84.998 (after the T-156 (1) fix); CM7 std 0.04302 (0.04308), mean 0.4998, corr_rg 1.0 / 0.49995 at Chroma 0.5; CM8 0.1794 (0.18) | handheld doc + Trail 1 + ISO 400: GPU 2.9-3.5 + CPU 0.7 (geo 1.0, acc 0.7-1.4, fx 0.9 GPU; path 0.2 CPU); without trail ~1.0 GPU (geo 0.5, fx 0.2, multi-op sampler) |
| dof | DF1 coc vs `coc_px(plane_depth)` max 0.016-0.05 px (rows 960 / 1400 / 1800 / 200 = 0 / 9.82 / 19.81 / -17.77); DF2 rows 930-990 out = in (0); DF3 disc half-max radius 25-30 px (32 taps) / 26-29 (64) for 30 after the mip-lod fix (T-156 (3); before 5-21); polygon vertex / edge 1.04 with the gather alone, **1.09-1.13 with the highlight sprites (polish 27 Oct, passed)**; DF4 AF point af 0.74997 (0.75), bpm rack follows Focus / Focus2 per beat | portrait f1.4 (32 taps): GPU 1.1 + CPU 0.5 (coc 0.37, gather 0.57); hex night 48 taps gather 0.73-0.87 GPU |
| gate | GA1 off on clip 0; rows 452 (452), 1.85 584 (584), 2.39 rotate fit 804 cols (803 +-2); GA2 mid 0.7896 (0.7901), corners 0.2502 (0.25); GA3 frame lines centred at 639 / 1279 (every 640, 14 px), 4 holes per cell per band, 12 per side | super 8 gate: fx 0.53 GPU + 0.1 CPU; + swirl / glow / microcontrast / strip: fx 0.87 GPU |
| colour | CO1 clip 0, patches max 0.0039 (1 16F step at values 4-8; < 2e-3 relative); CO2 logview 0.3909 (0.391), ACES view 0.3582 (0.3584 for the 16F input), exp 0.3596, CDL 0.3555, LGG 0.6597, WB (0.2303, 0.1685, 0.1400) - all within 3.3e-4 of `colour_px`; mixed grade linear + log on patches within 2e-3 relative (HDR outputs to 166); CO3 strips = `cube_strip(parse_cube)` exactly (18 x 289), tetrahedral / trilinear, Lutmorph 0.5, Lutmix 0.5 on patches + ramp: max rel err 9e-4 / 5e-4 | log grade + 2 LUTs + ACES view: fx 0.65 GPU + 0.15 CPU |

**Polish 27 Oct (b4 Build4.86 -> main by builder, `JazibTD_home.470.toe`; T-161):** only `dof1` and `camera1`
re-built in main with `F['_instance']` (FX_film un-parked, one module per exec, frames between, forced a cook of the
new passes: errors 0, 4183 ops; parked, saved). No pixel reads in main.
- **dof highlight sprites** (`hl` pass + sprite list in the gather; pars Sprites 1.0, Spritethr 0.8): DF3 polygon
  **passed**: vertex / edge half-max 1.10 / 1.13 / 1.09 at lights (540, 960) / (200, 300) / (880, 1600) (Taps 64:
  1.10 / 1.13 / 1.08; Bladerot 30 -> 0.91 / 0.89 / 0.92; Sprites 0 -> 1.05 / 0.99 / 1.03 = the old gather); disc
  half-max 29.4 / 29.9 / 29.3 (30); out energy 2239.8 (in 2240, every case). DF1 max 0.031 px (0 / 9.84 / 19.83 /
  -17.75), DF2 rows 930-990 = 0, DF4 af 0.74999, Amount 0 = 0. Capture
  `output/project1_lab_FX_film_dof1_out1_2026-10-26T18-52-03-060Z.png` (hexagons on the lights chart). Cost (portrait
  f1.4 on the clip): hl 0.24 + gather 0.75-1.0 (sprites off 0.65-1.14 in the same minutes) + coc 0.24-0.35 + fx 0.16
  GPU; worst case every tile lit (Spritethr 0.5 on the clip): gather +0.35-0.47.
- **camera Trail fused** (`acc` = geo maths + trail, one rgba32float buffer, geo not cooked while Trail is on): handheld
  doc + Trail 1 + ISO 400, same minutes A/B/A: old geo 0.65-0.76 + acc 0.42-0.48 GPU (+0.25 CPU) -> new acc 0.63-0.75
  GPU (+0.17 CPU); module total ~2.3 -> **~1.7 ms** (path 0.04 + 0.23 CPU, ae 0.03, fx 0.40-0.45). CM6 a 0.96721 (59/61),
  n 11.998 / 20.998 / 30.998; CM1 static patches with Trail 1 (settled) and Trail 0: out = in (0); Amount 0 = 0.

Fixes made live (offline tests 57 green after each): camera `acc` time-correct decay + 30-frame restart, `ae` / dof
`af` 30-frame restart (T-156 (1)); colour LUT Script TOPs cache in `.storage` (cook-loop warning gone, T-156 (2)); dof
gather tap colour at mip lod (T-156 (3)). Cosmetic: `stage_3_Out/annotation/back` warns about a missing
`FX_film/annotate/annotation` path on b4 (TD annotate internals after the re-layout; no effect).

## Not done / open
- **Wave C cost under load:** camera with Trail now ~1.7 ms on b4 under 5 TDs (fused acc, below); colour / gate /
  dof 0.6-1.6 ms each: over the prep targets with 6 TDs on the GPU; re-measure on a quiet machine. Next camera step if
  needed: the ISO noise (fx 0.4 ms: 8 hashes + log per pixel). acc at half res / 16F was not taken (CM6 needs 32F,
  half res would soften the trail).
- dof sprites are one per tile (T x T coc texels): two lights closer than a tile merge into one sprite at their
  centroid (T = 8 at Maxblur 30, half res = 16 px). Fine for bokeh; a per-light list would need atomics into a buffer.
- **Perf lane 3 (27 Oct, b2):** glow pair = ext + pyra + pyrb + glow (gather at the Quality res) + fx (full-res
  composite): halation 3.11 -> 1.34 ms, diffusion 4.06 -> 1.63, dof (hl per-thread tiles) 2.61 -> 2.09, paired;
  Quality `full` keeps the old per-pixel gather. Numbers and parity: docs/builds/PERF_QUIET_27OCT.md "Perf lane 3".
  **In main** (27 Oct, 31550, T-207): rehearsed on b2 on a 14-module panel-carrying copy (old builder 82d203f^), then
  main: halation1 / diffusion1 / dof1 by `_instance(c, name, module, panel=False)` (panels kept, 1.3-2.7 s each),
  `gate_upgrade` for the other 11, one per exec after un-park + frames; 14 gates agree with `<name>_slot`, errors 0,
  4181 ops, parked, `JazibTD_home.820.toe`; library re-exported. b2: rebuilt modules = fresh build bit-exact (diff 0).
- **Cost of the glow pair (before lane 3):** halation / diffusion gather all 8 levels at full res (fx ~1 ms GPU) and the 9 ops cost
  ~1 ms CPU. Next step if the stack must fit 3 ms: gather at EXT resolution and upsample in the composite (4x fewer
  gather pixels), or share one pyramid when both modules use the same threshold.
- `star` taps and `flare` ghost blur still read TD box mips with textureLod (arms 2-4 deg off at r 90, T-129 (5)):
  move them onto the PYR levels when a look needs it.
- Fair 60 fps numbers need a quiet machine (one TD, others parked); today's numbers are under 4-6 busy TDs.
- Rest of FX_film (weave, dust, tilt-shift, lens dirt, CCD artefacts, pulldown, HUD): later waves (FX3 s8). Wave C
  covers camera (C1-C4, C8), dof (L10-L11), gate (F8, L7, L12, distortion part of L6) and colour (S1-S3, S5).
- No mask / protect input (person, logos): add when a second module needs the same mask (FX_destroy has one).
- `leaks` and `flare` take no audio input; bind a CHOP to Level / Intensity / Trigger (shared trigger hub when a
  third module needs it).
- Linear-light handling: tonecurve / stock decode + encode (Inspace); the glow modules add in whatever space comes in
  (display space for 8-bit clips, like most VJ tools); a rack-level linear working space is not built.

## Sources
FX3 (F1-F4, F7, L1-L5, S4), FX0 rows 26-32, FX6 probes, LEARNINGS T-46, T-47, T-108, T-111, T-113 (5), T-114,
T-116 (1)(4)(6), T-117. Reused ideas: StageLab `JZB_Color_Bloom` (soft-knee prefilter), `JZB_Lofi_Grain` (second
lattice at 36.87 deg, film-rate hold), Narkowicz ACES fit (CC0/MIT), Hill ACES fit, Hable / Uncharted 2, Lottes 2016,
the classic bleach-bypass overlay, John Chapman's pseudo lens flare (re-implemented from the article), Jimenez IGN.
