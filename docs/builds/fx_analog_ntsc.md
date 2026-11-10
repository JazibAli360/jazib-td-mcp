# fx_analog_ntsc: FX_analog rack + 6 modules `ntsc`, `vhs`, `signalloss`, `crt`, `crtfault`, `plasma` (live in main, 26-27 Oct 2026, TD 2025.31550)

`/project1/lab/FX_analog`. This is the analog-signal rack from `docs/research/FX0_effects_backlog.md` (row 16, FX2 AV-10;
AV-11 PAL is a mode of this module, not a separate one). **Status: built live (see "Verified live" below; this head was written when it was only prepped offline).** Every TD fact
below is marked LIVE CHECK. The maths is pinned by a numpy reference, and the live lane diffs each pass against it.

- **Rack** = the FX_glitch rack, reused as it is. `builders/fx_analog.py` execs `builders/fx_glitch.py` and changes
  only `NAME` (`FX_analog`), the module file (`builders/fx_analog_<X>.py`) and the first row (`ntsc1`). It keeps the
  same `slots` table, Cross + Switch slots, Panic, add/remove/rewire and test clip (`docs/builds/fx_glitch.md`). No
  rack code is copied (no-bloat rule). Later analog modules (`vhs`, `crt`, ...) only add a `fx_analog_<X>.py`.
- **Module** files:
  - `builders/fx_analog_ntsc.py`: pars, presets, 4 compute shaders, build.
  - `builders/fx_analog_ntsc_logic.py`: the pure maths, copied into the instance's `ntsc_logic` DAT. It holds the
    uniforms, the frame phase, the numpy reference, the `parity()` LIVE CHECK helper and the test cards.
- **Tests:** `python3 -I -m unittest discover -s test -p 'test_fx_analog_ntsc.py'` runs 33 tests in ~8 s. They cover
  derive, kernels, the reference properties, the parity helper, the GLSL compile (glslc against TD compute stubs),
  the template and the rack.

## Build (td_exec)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_analog.py').read(), ns)
ns['build']('/project1/lab')                          # FX_analog + ntsc1 (idempotent)
ns['add']('/project1/lab/FX_analog', 'ntsc')           # ntsc2; ns['remove'](..., 'ntsc2'); ns['rewire'](c)
```

## Network inside `ntsc1`
| Stage | Ops |
|---|---|
| 1 In | `in1` (In TOP), `ntsc_logic` (Text DAT, the logic file) |
| 2 Encode | `enc` (compute, `rgba32float`, Samples x Lines): r = composite, g = Y, b = C (S-Video) |
| 3 Decode | `sep` (compute, `rgba32float`, signal res): r = Y, g = C after separation. `dec` (compute, `rgba16float`, signal res): RGB |
| 4 Out | `up` (compute, input size, `useinput`): back to the picture size, mixed by Amount. `wet` (Switch: Amount 0 -> `in1`). `out1` |

Every pass is compute mode (T-46/T-47) with `local_size 8x8` and auto dispatch. Each shader returns early past its
own size. Uniforms are vec4 expressions: `op('ntsc_logic').module.UNI(parent())['uX'][i]`. `UNI` caches on the
tuple of raw par values. The frame phase is `frame_phase(parent(), absTime.frame)` and the noise frame is
`absTime.frame % 16777216`.

## The maths (numpy reference = shaders, line for line)
- **enc.** Each signal sample (k, line r) is the mean of up to 4 x 8 texels of its footprint. Integer picks:
  `x0 = k*W/ws`, `x0 + i*span/nx`. The sample goes to YIQ (NTSC) or YUV (PAL). The subcarrier phase in cycles is
  `fract(cps*k + lineadv*r + fph)`:
  - `cps = Subcarrier * fsc / fs`, with `fs = Samples / active_us` and active_us = 754 / (4 x 3.579545) = 52.66
    (NTSC) or 922 / (4 x 4.43361875) = 51.99 (PAL). So the defaults are exactly 4 fsc, and cps = 0.25.
  - `lineadv` is 0.5 (NTSC, 227.5 cycles/line) or 0.75 (PAL, 283.75).
  - `fph = frame * Crawl * frameadv`. frameadv 0.5 gives the NTSC 2-frame dot-crawl repeat; 0.75 gives a 4-frame
    repeat for PAL.

  The chroma is `C = I cos + Q sin` (NTSC) or `U sin +- V cos` (PAL: the V switch flips sign on odd lines). The
  stored values are composite `(Y + C + n1) * Gain`, Y `(Y + n1) * Gain` and C `(C + n2) * Gain`. The noise n is
  triangular in +-Noise, from the same pcg hash as the dct module.
- **sep.**
  - none: Y = C = composite (full cross-colour, dots in luma).
  - notch: `Y = (c(k-d) + 2c(k) + c(k+d)) / 4`, with d = 0.5/cps samples (linear interp), and `C = c - Y`.
  - comb1: `(c(r) +- c(r-D)) / 2`.
  - comb2: `Y = (c(r-D) + 2c(r) + c(r+D)) / 4`.
  - S-Video: Y and C taken from enc's g and b.

  The comb delay D is 1 line for NTSC and 2 for PAL; both give `C(r-D) = -C(r)`. Edge lines mirror.
- **dec.** One loop over j in -R..R (R <= 24) along the line. Taps that fall off the line are skipped, and each
  channel is divided by its own weight sum. The kernel `kern(j, fc, R, Ringing)` has -6 dB at fc:
  - Ringing 0: Gaussian (no overshoot).
  - Ringing 0.5: Blackman-windowed sinc.
  - Ringing 1: bare sinc (Gibbs).

  The cutoffs are fc = bandwidth MHz / fs, and the half-width is R = ceil(1.2/fc), clamped to 2..24.

  The luma is `Y = (1+Peaking) * LP(Y, fcY) - Peaking * LP(Y, fcY/2)`. Demodulation is
  `a = 2C cos(th + perr)`, `b = 2C sin(th + perr)` (PAL: `2C sin`, `+-2C cos`). PAL-D averages line r with r-1 (the
  delay line). The chroma is then low-passed at Ibw / Qbw, rotated by Hue, scaled by Saturation and put through the
  inverse matrix.
- **up.** u = (x + 0.5) * ws / W - 0.5 is linear along the line. Vertically, the nearest line is mixed with the
  bilinear value by Lineblend. The result is `mix(in, rgb, Amount)` with the input's alpha.

## Pars (pages NTSC, Signal; zkit shows both)
| Par | What |
|---|---|
| Amount | 0 = exact passthrough (`wet` picks in1, nothing cooks), 1 = full |
| Standard | NTSC (YIQ 3.58 MHz) / PAL-D (YUV 4.43 MHz, delay line) / PAL-S (Hanover bars) |
| Separation | None / Notch / Comb 1H / Comb 2H / S-Video |
| Crawl | dot crawl speed: 1 = real (NTSC 180 deg per frame), 0 = frozen, fractional = slow slide |
| Hue, Saturation, Phaseerr | decoder tint (deg), chroma gain, demodulator phase error (deg; NTSC = hue shift, PAL-D = desaturation, PAL-S = Hanover bars) |
| Peaking, Ringing | luma overshoot (sharpness), filter shape (0 Gaussian, 0.5 windowed sinc, 1 bare sinc) |
| Noise, Gain | noise on the signal (composite + Y; C gets its own), signal gain |
| Samples, Lines | signal res (754 x 480 NTSC 4 fsc, 922 x 576 PAL; 640 x 240 = console) |
| Subcarrier | x real fsc (moves the dot pattern / cross-colour frequency; creative) |
| Ybw, Ibw, Qbw | MHz: luma 4.2, I 1.3, Q 0.5 (PAL: U and V use Ibw / Qbw, presets set both 1.3) |
| Lineblend | 0 = hard 4 px lines (at 1920 / 480), 1 = smooth |
| Seed | noise seed |

Presets (zkit 1-5): 1 broadcast (NTSC, Comb 2H, peaking 0.2), 2 cheap tv (Notch, narrow bandwidths, peaking 0.7,
ringing 0.5, noise 0.03), 3 dot crawl (None), 4 console 80s (640 x 240, Notch, Crawl 0, hard lines), 5 pal hanover
(PAL-S, Comb 1H, 922 x 576, phase error 20).

## Reference numbers (numpy, 1080x1920, defaults unless named; from `reference()`, 8-bit inputs)
| Input | Mode | Expected out vs in (max / mean abs, % pixels changed > 1/255) |
|---|---|---|
| Constant grey 128/255 | Notch, Comb 1H, Comb 2H, S-Video | 0 / 0 / 0 % |
| Constant grey 128/255 | None | max 0.227, mean 0.0015, 7.6 % (colour fringe in the ~R samples = ~34 px at the left/right line ends; interior < 0.01) |
| Constant red (191,0,0) | None | max 0.405, mean 0.050, 97 % (dots in luma: interior luma peak-to-peak 0.41) |
| Constant red | Notch | max 0.307, mean 0.0008, 2.3 % (line ends only) |
| Constant red | Comb 1H / 2H / S-Video | max 0.099, mean 0.0002, 1.5 % (line ends only) |
| Red, NTSC, Phaseerr 20, Comb 1H | | hue +20.0 deg on every line, sat x1.000 |
| Red, PAL-D (922), Phaseerr 20 | | hue 0.0, sat x0.9397 (= cos 20) |
| Red, PAL-S (922), Phaseerr 20 | | hue -20 / +20 on alternate lines (Hanover bars) |
| Red, None, frame 0 vs 1 / vs 2 | | max diff 0.414 / 0.0 (dot crawl 2-frame repeat) |
| fsc-frequency luma stripes on the signal grid | None, Notch | false colour mean abs I/Q > 0.1; Comb / S-Video 0 |

## LIVE CHECKS (about 15 min; register the lane first: `python3 tools/lane.py add FX_analog "<agent>"`)
- **N1 build.** Run the build lines.
  - Expect `td_errors` to be clean on all 4 GLSL TOPs. These are real TD compiles; offline was glslc only.
  - Check that format names `rgba32float` / `rgba16float` are accepted by the compute GLSL TOP.
  - Check that `enc` is 754x480, `sep` and `dec` are 754x480, `up` and `out1` are 1080x1920.
  - `ns['rewire'](op('/project1/lab/FX_analog'))` returns 0 on the second call.
  - Then `td_layout`, then capture.
- **N2 parity (the key check).**
  - Set Crawl 0 and Noise 0. Pause `test_clip` (`op('/project1/lab/FX_analog/test_clip').par.play = 0`). Wait a few
    frames.
  - In a **separate** exec (T-74): `m = op('/project1/lab/FX_analog/ntsc1'); m.op('ntsc_logic').module.parity(m)`.
  - Expect: enc <= 2e-5, sep <= 2e-5, dec <= 2e-3 (half float), up <= 6e-3 (8-bit out + half-float dec).
  - Repeat for Separation none / notch / comb2 / svideo and for Standard pald / pals with Samples 922. Same limits.
  - If a pass misses: diff that pass alone. Each pass reads only its own input, so the first one that fails is the
    bug.
- **N3 parity with the crawl running.** Set Crawl 1. `parity()` reads the fph/frame uniforms at the time of the exec.
  If the texture is one frame older, the diff for enc is about 0.3 and not 2e-5. Then repeat the read with
  `project.pause` / `play = 0` of the timeline. If that gives exactly 0 it is a timing artefact, not a bug: record
  which one it was.
- **N4 constant inputs.** Wire a Constant TOP (8-bit, 1080x1920) into FX_analog in1 (Input auto), with the numpy
  read of `img_src` vs `out1`:
  - grey 128 with Comb 1H gives max diff 0.
  - grey with None gives max ~0.23 at the line ends only. Columns 40-1040 should be < 0.01.
  - red (191,0,0) with None gives interior luma peak-to-peak ~0.41.
  - red, NTSC, Phaseerr 20 gives a hue shift on all lines. With PAL-S (Samples 922) adjacent 4 px line rows show
    alternating tints. With PAL-D they don't.
- **N5 passthrough** (the same method as FX_glitch). Amount 0 gives max diff 0, and `enc` does not cook (cook count
  frozen). Slot enabled 0 or mix 0 gives 0. Panic on gives 0.
- **N6 dot crawl.** None + Crawl 1 on the test clip: a capture shows the crawling dots on colour edges. Crawl 0
  freezes them. Read `out1` on 3 consecutive frames (Execute DAT onFrameEnd, T-47 recipe). Frames n and n+2 should
  be equal and n+1 different (NTSC). This needs the clip paused.
- **N7 presets.** zkit Recall 1-5 sets the pars exactly. Take one capture each: broadcast, cheap tv, dot crawl,
  console 80s, pal hanover.
- **N8 cost.** Pull out1 per frame and sum the cpu + gpu of enc/sep/dec/up/wet over 120 frames (the fx_glitch
  method), test clip excluded.
  - Estimate: enc ~0.1, sep ~0.05, dec 0.2-0.5 (49 taps, 4 kernels per tap evaluated in-shader), up ~0.2. **Total
    ~0.6-1.0 ms.** Budget 3 ms. The project should stay at 60 fps (cookRate untouched).
  - CPU: the uniform expressions should be ~0 ms while pars are static. If TD re-evaluates them every frame, CPU
    shows ~0.5 ms+. In that case record a LEARNINGS entry and move `UNI` behind one Python cache per frame.
  - If dec is over 1 ms, the first fix is to precompute the 4 kernels into a 49x1 `rgba32float` compute pass once
    per par change.
- **N9 wrap-up.** td_errors clean, `td_checkpoint`, save, park FX_analog, `lane.py remove FX_analog`. Add the
  measured numbers to this file's "Verified live" section, and LEARNINGS T-nn for anything that surprised.

## Verified live (26 Oct, 31550; scratch TD with other lanes, then brought home to main)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- **N1:** 4 compute GLSL TOPs compile clean (`td_errors` empty); formats rgba32float / rgba16float accepted; enc / sep /
  dec 754x480, up + out1 1080x1920; second `rewire` = 0; `td_layout check` ok.
- **N2 parity** (Crawl 0, Noise 0, clip paused, separate exec 3 frames later): enc 0, sep 0, dec 9.76e-4, up 2.6e-3
  to 2.7e-3 for NTSC None / Notch / Comb 1H / Comb 2H / S-Video and PAL-D / PAL-S (922). Bug found: `parity()` compared
  the 8-bit `up` with the unclipped reference (peaking overshoot 1.018 -> 0.018 "error"); it now clips the reference
  when in1 is fixed-point.
- **N3:** Crawl 0.5 / 1 running: same numbers with fph 0.25 read back (texture and uniform from the same frame).
- **N6 dot crawl** (Execute DAT onFrameEnd, out1 per frame; scratch ran ~30 fps so absTime stepped by 2): Crawl 1 ->
  frames 2 apart identical (2-frame repeat); Crawl 0.5 -> 12 frames apart 0, 13 / 3 apart 0.157-0.169; Crawl 0 -> 0.
- **N5:** Amount 0, slot enabled 0, mix 0, Panic: max diff 0 (img_src vs out1, two reads each).
- **N7:** zkit Recall 1-5 sets every preset par exactly (the very first Recall right after build missed broadcast's
  Peaking / Separation once; every later run exact).
- **N8 cost** (out1 pulled, sum cpu+gpu of ops cooked with out1, 120 frames, scratch TD shared with other lanes):
  comb1 default 2.35 ms median (dec 0.81, enc 0.31, up 0.20, sep 0.10), cheap tv 2.59 (dec 1.28), pal hanover 2.30.
- Main TD: loaded from `output/transfer/FX_analog.tox`, `td_errors` clean, restaged, parked, saved (JazibTD_home.276).
- Capture: `output/project1_lab_FX_analog_out1_2026-10-26T15-02-38-276Z.png` (cheap tv), scratch window
  `output/window_TouchDesigner_2025.31550_Users_vyro_Docu_2026-10-26T15-02-47-677Z.png`.

## Perf lane 2 (27 Oct, b2, 31550)
- `dec`: the 4 x 49 tap weights are filled once per 8x8 group into shared memory (`KW[49]`, lanes 0-48, `barrier()`),
  and the subcarrier phase per tap advances by a fixed rotation (cos/sin once per pixel). Paired same-frame A/B (old vs
  new copies, T-145): dec GPU 1.20 -> 0.45 ms (0.38x). Module solo on b2 (loaded machine): 2.24 -> 1.66 ms median.
- Parity on b2 after `upgrade`: enc 2e-7, sep 2e-7, dec 9.7e-4, up 2.5e-3..2.8e-3 for NTSC comb1, PAL-D 922 + phase
  error 20, PAL-S, NTSC None + Ringing 1 + Peaking 0.7 (same as before).
- Also seen: the GLSL TOPs' Python uniform expressions are cheap while pulled normally (dec CPU 0.15 ms), but a
  `cook(force=True)` re-evaluates all 24 of dec's: 1.9 ms CPU (constants on a copy: 0.04). Paired A/B numbers on this
  module are therefore CPU-inflated; read the GPU column.

## Not done / open
- SECAM, RF, interlace, artifact colour (AV-11..14) are later modes or modules. The `enc` pass is their hook. For
  example, Raw mode (AV-12) would skip the RGB -> YIQ step.
- No burst / sync / blanking is modelled. Line ends use one-sided filter taps, so None/Notch show a ~30 px colour
  fringe there. That is authentic overscan junk; crop with a Crop TOP if it is unwanted.
- The kernels are evaluated per tap in the shader. A precomputed weight texture is the first optimisation if N8
  needs one.
