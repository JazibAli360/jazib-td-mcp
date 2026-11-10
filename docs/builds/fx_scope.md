# fx_scope: FX_scope rack + 5 modules `xy` `vector` `lissajous` `scopes` `hud` (live in main, 26 Oct 2026)

`/project1/lab/FX_scope`. FX0 Phase 4 lane C (`docs/research/FX0_effects_backlog.md` rows 25, 58; FX2 AV-30..33, FX3 C6,
FX5 G19 / G38). Scopes, vector displays and the camera HUD, as one rack. **Built live 26 Oct (31550): all five
modules in the main .toe, see "Verified live" for which LIVE CHECKS ran and their numbers.** Offline status: `python3 -I -m unittest discover -s test -p 'test_fx_scope*.py'`
(39 tests: specs, presets, every par expression evaluated on a fake TD, numpy references, glslc compile of all 14
shaders x 4 build switches, dry builds on a fake TD). One owner: the FX_scope prep lane (T-119); every file is
`fx_scope*`.

## Files
| File | What |
|---|---|
| `builders/fx_scope.py` | the rack: `builders/fx_glitch.py` exec'd as is (like `fx_analog.py`), NAME `FX_scope`, first row `xy1`, modules from `fx_scope_<m>.py`; `build` / `add` also return `missing` (par names this build lacks) |
| `builders/fx_scope_beam.py` | the beam engine the three line modules share (xy, vector, lissajous): shader assembly, the Beam / Phosphor / Display pages, uniform expressions, CHOP texture-buffer chain, `build_engine`. Switches `BUFFERS`, `ATOMICS` (see X0 / S0) |
| `builders/fx_scope_logic.py` | pure maths + numpy references (beam splat, phosphor, paths, figures, scope counts, HUD), par-expression lambdas, own 8x8 font copy, readback snippets + `check` CLI |
| `builders/fx_scope_xy.py`, `_vector.py`, `_lissajous.py`, `_scopes.py`, `_hud.py` | the modules (template: `docs/builds/fx_glitch.md` "Module template") |
| `builders/glsl/fx_scope_*.glsl` | lib, audio, path skeleton, src_xy / src_vector / src_lissajous, beam, glow, look, hist, scopes, hud |
| `test/test_fx_scope.py` | the offline tests |

## Build (td_exec, ~3 min)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_scope.py').read(), ns)
r = ns['build']('/project1/lab')                 # rack + xy1; idempotent. r['missing'] must be {'xy1': ''}
for mod in ('vector', 'lissajous', 'scopes', 'hud'):
    r = ns['add']('/project1/lab/FX_scope', mod)  # vector1 ... hud1, wired last; r['missing'] must be ''
```
Lane rules first (CLAUDE.md): `python3 tools/lane.py add FX_scope "<label>"`, `FX_scope.allowCooking = True`, other
idle COMPs parked (never one another lane touched in the last minutes), `td_checkpoint` after each verified step,
`td_layout` flow, `td_errors` clean (`/project1/lab/FX_scope`, includes Script errors). Build each module in its own
exec (structural calls one at a time, T-31). Risky first runs (new shaders) go on a build TD (`target:'b2'`, T-120),
then `td_bring_home`, re-check, park, save in main. Rebuild = the same calls (idempotent: ops reused by name, pars kept).

## Rack
Exactly the FX_glitch rack (`docs/builds/fx_glitch.md`): `slots` table (name module enabled order mix), per slot module
COMP -> `<name>_mix` (Cross) -> `<name>_slot` (Switch 0 bypass / 1 module / 2 mix), Panic, `Input` auto/live/test.
Slots run in series: e.g. scopes1 after xy1 measures the scope picture; a HUD last frames everything.

## Beam engine (xy, vector, lissajous)
`[CHOPs] -> path -> beam -> glow -> look -> out_sel -> out1`, all compute GLSL (T-46/T-47):

| Op | What |
|---|---|
| `src_none`, `sel_<k>`, `src_xy` (+ `src_rgb`) | Constant fallback (0, channels named like the Chan pars), one Select per channel from the source CHOP, Merges in fixed order -> GLSL Arrays page texture buffers `uXY` vec2 (+ `uRGB` vec3), T-110 pattern |
| `path` 1024x17 rgba32f | the module source (`scopeCount` / `scopePoint`) -> up to **16384 points / frame** in beam px: texel = (x, y, weight of segment j -> j+1, packed rgb); row 16 = per 256-point chunk bbox of the lit segments + the count. Rotate, gains, Noise jitter. Cooks every frame (uniform absTime.frame) |
| `beam` rgba32f, 2 colour buffers, readwrite, clearoutputs off | 16x16 workgroup = 32x32 px tile, manual dispatch. Chunks whose bbox (grown by 5 sigma) miss the tile are skipped without a barrier; else each thread tests one segment, hits go to shared memory (shared `atomicAdd`; scan fallback), every pixel sums them: `E += Kn I w [Dwell dt G/L + (1-Dwell) G/Lref]`, G = the 2D Gaussian integrated along the segment (erf, A-S 7.1.26), point form (midpoint) under 0.02 px. Then phosphor: `S = S_prev exp(-dt/tau_c) + E A`, alpha = luma(E) (flash). Buffer 1 = per-texel (last absTime.frame, 1, w, h): a repeat cook in the same frame (readback, T-116 (4) / T-117) keeps the texel; a gap > 0.25 s or a size change restarts from 0 (no stale trails after a bypass) |
| `glow` rgba16f, 1/8 | display energy at mip lod 3 (`inputfiltertype mipmap`), near + 3x wide 7x7 Gaussians; `glow_src` = 1x1 black while Glow is 0 (not cooked) |
| `look` input size, useinput | panel = beam buffer mapped to (Centre, Size, Aspect); `1 - exp(-Exposure (D + Glow G))` (hot cores burn to white), cellophane overlay (vector), graticule (scope grid + minor ticks / polar / cross), correlation meter (goniometer), Background add / dim / black / screen, Amount. Outside the panel = texelFetch of in1 (exact) |
| `out_sel` | Amount 0 = in1 exact; nothing upstream is pulled |

Normalisation (`logic.beam_consts`): beam buffer = panel x Quality (full / half / quarter, >= 32 px), sigma =
Beamwidth x Quality (>= 0.35 px), Lref = min(beam w, h), units +-1 = +-Lref/2 (Fill: +-w/2, +-h/2), `Kn = Lref
sqrt(2 pi) sigma`. So: **the energy per frame is Intensity x Kn whatever the figure** (Dwell 1), and a line one Lref
long drawn once per frame peaks at Intensity, at any beam width or Quality. Dwell 1 = physical scope: brightness
inversely proportional to beam speed (corner dwell and slow passages glow, fast jumps fade); Dwell 0 = even line.

**Budget** (default 1024): a tile stops summing after that many hit segments in a frame, so the per-pixel work is
bounded whatever the signal (offline counts, worst tile at Quality half: xy defaults 111, lissajous 4096 pts 127,
16384 pts 504, 800-sample Gaussian noise x4 oversampled 424). Over budget = the rest of that frame's segments are
missing in that tile only (P2 measures it).

Phosphors (afterglow tint / flash tint / tau multipliers): P1 green, P31 green-blue, **P7 blue flash + yellow
afterglow** (blue decays 3x faster), P4 white, P3 amber, source colours (RGB, for vector colour / rainbow), custom
(Tint r g b). Persist = tau in seconds (frame-rate independent, dt from absTime.frame / cookRate).

Shared pages: Beam (Intensity, Beamwidth, Dwell, Quality, Noise, Budget), Phosphor (Phosphor, Persist, Afterglow, Flash,
Tint r g b), Display (Size, Aspect square / fill, Centre X Y, Rotate, Exposure, Glow, Glowradius, Graticule,
Gratstyle, Divisions, Background, Bgdim). Slider ranges only, no clamps (no limits).

## Module `xy` (AV-30, G19)
X / Y = two channels of any CHOP (`Audiochop`, `Chanx` / `Chany`, default chan1 / chan2: point it at an Audio
Device In / Audio File In; this module only reads, never opens a device or plays sound) or **test tones** (Source
test, default: 110 Hz x, ratio 1.5, phase 90 deg, amp 0.8, 48 kHz -> 800 samples / frame, phase runs on across frames).
Catmull-Rom Oversample K (default 4: 3197 points from 800 samples); past 16384 points it decimates. Gain X / Y, Swap.
Presets: 1 green scope, 2 oscilloscope music (P31, black, no graticule, x8), 3 radar P7 (polar, 1.5 s afterglow),
4 white vector, 5 amber over picture.

## Module `vector` (AV-31)
Path source **by reference**: Source `chop` reads any `x y [r g b]` stream; `Pathchop` defaults to
`/project1/lab/LP_laser_path/out1` (LP's optimised, resampled, corner-dwelled, blanked path; Own engine = whole image
per cook, Native = 800 time-sliced samples). Source `sop`: `Pathsop` (any SOP) -> `sop_path` Script CHOP running LP's
own `laser_path_logic.run_engine` read-only (constant-speed Step, Vertexhold ms at Pps, blanked travel, nearest
order); it cooks only when the SOP or its pars change. Segment j is lit by sample j+1's colour (blank = max channel <
Blank), weight = that max x flicker, colour normalised to full hue. Colour white = no blanking. Monitor page:
Overshoot (corner ringing along the second difference), Flicker (square, frame-locked: 30 Hz = every other frame),
cellophane Overlay (Split, top / bottom colours). Presets: 1 Vectrex, 2 Asteroids, 3 Battlezone overlay, 4 Tempest
colour (source phosphor), 5 scope trace. **LP_laser_path parked = no picture** (T-118 (1)): un-park it or use sop.

## Module `lissajous` (AV-32, G38)
Figure: lissajous (a, b, Phase, Drift; Lock = integers, closes at Turns 1), harmonograph (two damped pendulums per
axis: a b + c d, Pendmix, Damping, Length; **Pen** = the pen draws [tau - Penspan, tau], tau = absTime x Penrate mod
Length, with Persist the figure builds up live), spirograph (hypotrochoid R r d, closes after r / gcd(R, r) turns),
rose (n / d), goniometer (M / S of the Audio CHOP, mono = vertical line; correlation meter at the panel bottom, green
in phase / red out; 440 Hz test pair 30 deg apart without a CHOP). Rainbow colours by path position (with Phosphor
source), Hue / Huespeed. Points 256-16384. Presets: 1 knot 3:2, 2 harmonograph pen (P7), 3 spirograph rainbow, 4 rose
5/4, 5 goniometer.

## Module `scopes` (AV-33)
`hist` (compute, manual dispatch) counts the input sampled every `Step` px (default 4: 270 x 480 at 1080x1920) into a
bins texture with per-tile shared-memory atomics (no image atomics, FX2): waveform (Sx x Levels), RGB parade (3 Sx x
Levels), vectorscope (Bins x Bins over Cb / Cr +-0.5, Rec.709 / 601), histogram (Levels x 4 rows R G B luma, row max in
g). `fx` draws it in the panel over the dimmed picture: intensity `1 - exp(-Gain n / ref)`, colours (green / white /
colour: parade channel colours, vectorscope = the colour at that Cb / Cr), graticule (0 25 50 75 100 %, legal 16 / 235
dashed, parade separators; vectorscope 100 % circle, 75 / 100 % bar targets, 123 deg skin line; histogram quarters).
Layout overlay (Size of W, Panelratio, Centre; vectorscope square) or full frame. Presets: 1 waveform, 2 RGB parade,
3 vectorscope, 4 histogram, 5 scope wall (full-frame parade). Engineering use: LED-wall clip / crush shows on the
waveform's 100 % / 0 % lines.

## Module `hud` (C6)
One pass: zebra (Zebralevel .. Zebraupper, moving diagonal stripes; a band < 1 for skin), focus peaking (|Sobel| / 4
> Peakthresh, colour, mono picture), false colour (exposure bands of our own: purple < 2.5 %, blue < 4 %, green 38-42
% (18 % grey), pink 52-56 % (skin), yellow 97-99 %, red >= 99 %; spectrum; 11 zones; clip / crush), clip + crush
warning (2 Hz blink), frame guides (16:9 2.39 1.85 4:3 4:5 1:1 9:16) with outside dim, safe areas, centre cross, corner
brackets, REC + blinking dot / STBY, timecode (run time from Tcreset + Tcoffset, or time of day; Tcfps), battery (red
under 20 %), Label (16 ASCII chars). Font: public-domain font8x8 ASCII (own copy in `fx_scope_logic.FONT_HEX`), drawn
with a dark 1-px outline. Hudscale = px per font pixel (4 -> 32 px text on 1080 wide). Presets: 1 camera REC, 2 exposure
check, 3 focus check, 4 cinema 2.39 guides, 5 LED clip check.

## LIVE CHECKS (each with the expected number; ~40 min in total)
Setup: rack `Input` = test, `op('/project1/lab/FX_scope/test_clip').par.play = 0` (paused), other slots enabled 0.
Readbacks in their own exec >= 2 frames after the change (T-74); parity sets via the snippets:
`L = {}; exec(open('<repo>/builders/fx_scope_logic.py').read(), L)` then td_exec the text of
`L['beam_snippet']('/project1/lab/FX_scope/<m>1', '<repo>/output/fx_scope/<check>')` (or `hist_snippet`), then offline
`python3 -I builders/fx_scope_logic.py check output/fx_scope/<check>`.

| # | Check | Expected |
|---|---|---|
| R1 | every module builds, `td_errors` clean, `missing` empty; GLSL compiles in TD (glslc offline is not a TD compile) | 0 errors, 0 warnings except the first-cook ones |
| X0 | texture buffer mapping: xy Source chop on a Constant CHOP (chan1 0.25, chan2 -0.5, 4 samples), path texel 0 | x = 243 + 0.25 x 243 = 303.75, y = 243 - 0.5 x 243 = 121.5 (default panel, half). Else set `BUFFERS = 'split'`, rebuild, re-check |
| S0 | shared atomics: scopes waveform `hist_snippet` on the paused clip | `check`: equal_bins >= 0.999 (float bin edges), total 129600. Else `ATOMICS = False` (gather fallback, slower) |
| B1 | xy defaults, Persist 0, `beam_snippet` | np 3197; alpha sum = Kn = **913.67** (+-0.1 %), max ~0.46; `check` rel < 1e-3 |
| B2 | xy Testratio 1, Testphase 90 (circle r 194.4 px) | alpha sum 913.67; ring brightest ~0.435 (arc traced twice), dimmest ~0.217 (once) |
| B3 | B2 with Dwell 0 | alpha sum ~4205 (= Kn x traced length / Lref), peak ~2.0 |
| B4 | lissajous defaults, Drift 0 (static), Persist 0, `beam_snippet` | alpha sum 913.67, max ~0.38; `check` rel < 1e-3 |
| B5 | Quality full vs half (B1) | alpha max equal within 5 %, sum x4 (Kn doubles with Lref and sigma) = 3654.7 |
| B6 | phosphor: B1 with Persist 0.1; set Intensity 0; read the `beam` rgb sum in two later execs, noting absTime.frame each time | sum ratio = exp(-dframes / (cookRate x 0.1)) within 1 % (dframes = frame difference; frame-rate independent) |
| B7 | repeat cook: two `beam` numpyArray(delayed=False) reads in one exec | identical (max diff 0) |
| B8 | slot enabled 0 for 1 s (pane elsewhere, T-122 (4)), then 1; read at once | no old trail: alpha sum = one frame's energy (913.67 in B1 setup) |
| B9 | Amount 0, slot enabled 0, mix 0, Panic; Size 0.5: rows outside the panel | max diff vs img_src 0 (all four), outside-panel rows 0 |
| B10 | glow: Glow 1 vs 0 | a soft halo (look mean rises, no blocks). If mip sampling of the 32F state fails, put a Resolution TOP (1/8, mipmap) between `beam` and `glow` (T-113 (5) pattern); the state stays 32F (buffer 1 holds absTime.frame) |
| V1 | LP_laser_path un-parked, pattern square, Engine own; vector defaults | path count 341 (LP's square), corner blobs: luma at a corner / edge midpoint > 3 |
| V2 | Source sop, Pathsop = a Rectangle SOP 1.6 x 1.6 (or a 4-point closed poly at +-0.8) | sop_path 337 samples (LP engine: 4 x 80 edge + 4 corners x 4 hold + 1, our logic's number), 0 blank |
| V3 | Overlay on, Split 0.82 | panel top 18 %: green / blue channels x0.25 / 0.2 of red (white P4 beam) |
| L1 | goniometer on an Audio File In (stereo music), Meter | trace mostly vertical; meter 0.3-1.0 (green) for typical mixes; swap one channel's sign (Math CHOP) -> negative, red |
| L2 | harmonograph pen, P7, Persist 2.5 | figure builds over ~15 s (Length 60 / Penrate 4), restarts at tau wrap |
| S1 | Constant TOP 128/255 grey -> FX_scope in1 (Input live): histogram | rows R G B luma: bin 128 = 129600 each, all other bins 0 |
| S2 | Constant 191/255 red: vectorscope (256 bins, 709) | one bin (106, 223) = 129600; trace dot on the R 75 % target box |
| S3 | Ramp TOP horizontal 1080x1920: waveform | each of the 270 columns exactly one lit level, count 480 |
| S4 | parade / histogram on the paused clip, `check` | equal_bins >= 0.999; totals 388800 / 518400 |
| H1 | hud Amount 0 / bypass | diff 0 |
| H2 | zebra on the Ramp TOP, Zebraspeed 0, others off | changed px = `zebra_mask(luma(src), 0.95, 1, 8, 45)` count exactly (about 50 800 for a (x+0.5)/W 8-bit ramp) |
| H3 | false colour exposure on the ramp | columns in 0.38-0.42 green (~46 of 1080), >= 0.99 red (~11) |
| H4 | peaking on the paused clip, Peakmono off | peaking px = `sobel_mag(luma) > Peakthresh` count (parity, +-0.1 % for float edges) |
| H5 | Tcreset, then 10 s later | timecode reads 00:00:10:xx (Tcfps 25), REC dot blinks 1 Hz, label text readable on white and black |
| P1 | cost, pane elsewhere, out1 pulled, 120 frames (T-100 / T-102 method) | xy defaults <= 1.5 ms; lissajous 16384 pts <= 2.5 ms; vector LP square <= 1.5 ms; scopes each mode <= 1 ms (vectorscope 256 is the heaviest); hud all on <= 0.8 ms; project 60 fps with all five on (report the real number) |

| P2 | worst case: xy on white noise (Noise CHOP 2 chans, 800 samples, time-sliced, amp 1), Dwell 0, Quality half, then full | frame cost stays bounded (<= ~5 ms half); if not, lower the Budget default and note it |

Write every live fact / bug to LEARNINGS (T-nn) as it happens; update this table with the measured numbers.

## Verified live (26 Oct, 31550; LEARNINGS T-132)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- **In main (perf lane 3 ops, 27 Oct, 31550, T-207):** the GLSL TOPs (+ `_compute` DATs) of xy1 / vector1 / lissajous1
  / hud1 recreated by builder (safe_destroy, then the rack's `_instance(c, name, module, panel=False)`: panels and
  slot_gate kept, new hud text without per-thread arrays), one module per exec; 5 gates ok, errors 0, 1732 ops, parked,
  `JazibTD_home.824.toe`; library re-exported. Rehearsed on b2 first: each module = a fresh rack build bit-exact
  (diff 0; xy / lissajous with Persist / Afterglow / Drift 0 so phosphor history does not differ).
Built on b4 (T-125 rule: FX_scope build/add on a side TD; rack + xy1, then vector 4.3 s, lissajous 8.6 s, scopes
5.6 s, hud 5.4 s), `bring_home.mjs --from b4` -> main (1727 ops = b4, 0 errors), parked, saved (JazibTD_home.366),
checkpoint `output/checkpoints/FX_scope/FX_scope_20261026-212848.tox`. Shaders ran first on the scratch TD
(`/project1/fxscope_lane`). Switches stay `BUFFERS = 'packed'`, `ATOMICS = True`.

| # | Where | Measured |
|---|---|---|
| bug | scratch | beam black: `unpackRGB` `uint(f + 0.5)` turns white 16777215 into 2^24 in float32 (all channels 0). Fixed: `uint(round(f))` (lib.glsl) + offline test |
| R1 | main | 5 modules, `missing` '' for each, `td_errors` clean, `td_layout check` ok (21 ops) |
| X0 | main | path texel 0 = (303.75, 121.5): exact |
| S0 | scratch | waveform on the paused clip: equal_bins 0.99997, total 129600 (= ref) |
| B1 | main + scratch | np 3197, alpha sum 913.665 (Kn 913.666), max 0.4642, `check` rel 4.2e-7 |
| B2 | scratch | sum 913.665; ring brightest 0.4346, dimmest 0.2173 |
| B3 | scratch | sum 4204.6, peak 2.0000 |
| B4 | scratch | np 4096, sum 913.666, max 0.3796, `check` rel 5.4e-7 |
| B5 | scratch | full 972x972: sum 3654.66, max 0.4653 (half 0.4642) |
| B6 | scratch | Persist 3, Intensity 0: ratio 0.889881 over 21 frames vs exp 0.889882 |
| B7 | scratch | two reads in one exec: max diff 0 |
| B8 | scratch | 1.8 s bypass, then on: alpha 913.66 (one frame), rgb 19942 vs 133834 steady (restarted) |
| B9 / H1 | main | all five slots Amount 0 in series, all enabled 0, all mix 0, Panic: max diff vs img_src 0 (each) |
| B10 | scratch | Glow 1: glow max 0.079, no NaN (mip lod 3 of the 32F state works), look mean 0.2767 -> 0.2796 |
| V2 | scratch | Rectangle 1.6: sop_path 337 samples, 0 blank; alpha sum 913.69, corner peak 3.29 |
| S1 | scratch | grey 128: rows R G B luma bin 128 = 129600, every other bin 0 |
| S3 | scratch | ramp: 270 columns, exactly one lit level each, count 480 |
| H2 | scratch | zebra (black, speed 0) on the ramp: 50818 px = `zebra_mask` 50818, 0 mismatches |
| H3 | scratch | false colour row: 46 green, 11 red px; row vs `falsecolour` max 0.002 (8-bit) |
| P1 | main | per-op sampler, 120 frames, pane elsewhere, other lanes cooking (main ran ~18-22 real fps either way, T-132 (4)): xy defaults median 1.7-2.5 ms (beam cpu 0.3 + gpu 0.4-0.9, path cpu 0.2-0.4); lissajous 16384 pts 3.8 ms (beam gpu 1.46); scopes vectorscope, clip playing 2.2 ms (hist 0.27 + 0.82 gpu; static input = no cooks); hud zebra + clip + peaking + safe + 2.39 guides 2.5 ms. Indicative only under that load |

Not run yet: V1 / V3 (LP_laser_path is another lane's COMP, parked), L1 (needs a stereo file), L2, S2, S4, H4, H5,
P2. Capture: `output/project1_lab_FX_scope_out1_2026-10-26T16-26-22-851Z.png` (xy over the clip + hud).

## Design notes / decisions
- **Compute-only, no Render TOP:** the beam is rasterised in a compute pass (tile binning + erf beam), not instanced
  quads in a Render TOP, so there is no Render-TOP CPU floor (T-112 (3): 2.2 ms at 262k), the result is a numpy
  reference to 1e-5 (check B1 / B4), and Kn makes brightness independent of resolution.
- **No image atomics** (FX2 AV-33 note). Shared-memory atomics only (scopes counts, beam hit lists); both have
  fallbacks behind `ATOMICS`.
- **Shared beam file** because three real modules use it today (no-bloat rule). The scopes / HUD share nothing but
  the shader loader.
- The HUD font is an own copy (public domain) because FX_retro's font file is another lane's uncommitted work.
- Phosphor state is frame-rate independent (tau in seconds) and survives readbacks (per-texel frame stamp).

## Not done / open
- Beam joins between frames: the first point of a frame does not connect to the last of the previous one (one
  segment gap per frame; hidden by persistence).
- `xy` has no Z (beam blanking) channel; `vector` blanks by colour. Add a Zchan when a real source needs it.
- No `ridgeline` / `spectro` modules (FX0 row 58 lists them for later).
- Beam Intensity per segment for vector streams uses the max channel; a separate `i` channel is not read.
- Glow mip lod 3 from a 32F state works (B10, scratch); its parity against a numpy reference is not measured.

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.748).
