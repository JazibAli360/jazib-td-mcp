# FX_synth: video-synth rack + 6 modules (live in main, 26 Oct 2026, TD 2025.31550)

Status: **built live in the main TD** (all six modules, slots left enabled 0, COMP parked, saved
JazibTD_home.362.toe, checkpoint `output/checkpoints/FX_synth/FX_synth_20261026-212428.tox`). Results: "Verified live"
at the end; the LIVE CHECKS below are the plan they answer. Specs: FX2 AV-22
(colorize), AV-23 + FX5 G24 (bands), AV-24 (keyer), AV-26 (ruttetra), AV-27 (scanimate), AV-28 (vfeedback), FX1 DG-22
(overflow); backlog FX0 rows 17-22. Rack + module template: `docs/builds/fx_glitch.md`.

`/project1/lab/FX_synth`. In: `in1` TOP. Out: `out1` TOP. The FX_glitch rack is reused unchanged, the same way
`builders/fx_analog.py` reuses it: the `slots` table, a Cross + Switch per slot, Panic, add/remove/rewire, the
`test_clip` input. `colorize1` is the first row. No module needs more than 3 GLSL inputs, so `_compute` is not
overridden.

Files (owner: the FX_synth lane only, T-119): `builders/fx_synth.py` (rack), `builders/fx_synth_<module>.py`,
`builders/glsl/fx_synth_*.glsl` (shaders, read by the module builders into docked DATs),
`builders/fx_synth_logic.py` (numpy references for every shader; never loaded in TD), and `test/test_fx_synth.py`
(43 offline tests: contract, logic defaults vs pars, a fake-TD build of every module (wiring, uniform names vs shader
declarations, every expression parses and names real pars), glslc compiles of 11 compute shaders + the MAT
vertex/pixel pair, plus the maths below).

```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_synth.py').read(), ns)
ns['build']('/project1/lab')                               # rack + colorize1
for mod in ('bands', 'keyer', 'ruttetra', 'scanimate', 'vfeedback'):
    ns['add']('/project1/lab/FX_synth', mod, enabled=0)    # bands1 ... vfeedback1, wired in order
```
Offline: `python3 -I -m unittest discover -s test -p 'test_fx_synth.py'` (43 OK, glslc 2026 Homebrew).

Shared rules for every module: Amount 0 sends `in1` through `out_sel` (Switch), so nothing in the module cooks. The
final passes also have their own `texelFetch` path at Amount 0. All GLSL TOPs are compute (T-46/T-47). State is
rgba16float. `stamp` is the 1x1 cook clock from FX_glitch feedbackkill (T-111): a gap > 0.25 s restarts the state
from live, and a second cook in the same frame is ignored (T-116 (4), T-117 (4)). It is shared by scanimate and
vfeedback, its only two users. Time uniforms only read `absTime` while something is animated, so a static setting
cooks only when its input changes. There are no limiters and no flash caps (user rule).

## Modules

| Module | Network | What it does | Presets |
|---|---|---|---|
| `colorize` | in1 -> fx -> out_sel | Paik/Abe phase colour: each channel is `f(Gain*x + Phase + Drift*t)`, with f = sine / triangle / saw / ramp and x = luma or R/G/B each into its own channel. The Hue mode maps luma to hue at Sat (Valuefollow). Then x Drive + Bias -> overflow clip / wrap / fold / solarize (Solar threshold). | paik phase, sandin sunset, solarize, neon fold, acid wrap |
| `bands` | in1 -> fx -> out_sel | Amplitude classifier: the signal (^ Curve) is cut into Bands. The fill is source (posterised) / grey / rainbow / duotone over source or black, and Softness blends across band edges. Contour lines of constant pixel width sit at every threshold (distance / central-difference gradient); every Major-th line is Majorwidth x wider. Offset + Speed + Wobble (LFO) move the thresholds, so the contours flow. | classifier, topo, posterise, neon contour, duotone flow |
| `keyer` | in1 + b_sel -> b_fit (Transform TOP) -> fx -> out_sel | Key A, optionally combined with key B by logic (and / or / xor / a-not-b / x / a>b), then Invert. Keys: luma window, chroma (CbCr distance BT.709 + Spill), shape generator (H/V wipe, iris, diamond, box, clock + Position fader, centre, angle), B luma, A alpha, one. The Op then uses the key: A over B / matte / alpha / add, multiply, min, max, difference, or bitwise xor/and/or on 8-bit levels where the key is 1. B is a colour or any TOP (Btop, fitted to A). | luma over colour, green screen, iris, xor logic, window x diamond |
| `ruttetra` | in1 -> mat (GLSL MAT) on geo (Grid SOP 2 x Samples, instanced Lines) -> render (additive, 16f) -> post (mip glow + persistence, fb) -> outc -> out_sel | The Rutt/Etra scan processor. The picture's signal is added to the deflection: `x' = x + Defx*s1`, `y' = y + Defy*s2`. Sources are luma / R / G / B / inverse luma. Wave and per-line jitter generators add to that, and the raster is then scaled, sheared, rotated and offset. Yaw / Pitch / Persp with Z relief give the td-port JZBN_RuttLines 3D look. Beam brightness follows the picture (Blank = beam off below a luma). Colour: video / mono phosphor / heat / rainbow by line. Width is in real px (the ribbon is expanded in screen space). Background: black / dimmed input / transparent. | classic relief, sideways scan, face wire, wave raster, rotating raster |
| `scanimate` | in1 + logo_text -> src -> warp -> fb -> stamp -> trail (16f) -> look -> out_sel | The Scanimate raster: fly zoom (Fly, Flyspeed) + spin, perspective taper, and a horizontal sine bend that travels along the lines. It works on the keyed source (Key / Keysoft). Trails = warp OVER (previous x Decay, zoomed / drifted / blurred). Look: trail age -> 4-stop palette (gold / sunset / electric / chrome / mono), with Bands for banded streamers. Logo colour keeps the source colours where the trail is fresh. Also raster lines, mip glow and background. Settle 1 = the clean, whole source. | flying logo, banded streamers, title settle, spin tunnel, rising slit |
| `vfeedback` | in1 -> fb -> stamp -> loop (16f) -> delay (Cache, optional) ; mix -> out_sel | Camera at its own monitor. Mirror (in loop) -> rotate / zoom / shift / barrel about the centre -> edge black (the monitor border) / mirror / repeat / clamp -> camera blur -> gain, gamma, contrast, hue step, saturation -> RGB stripe mask in the loop (moire) -> autogain toward Target -> live keyed in (mix / luma above / below, Inject + Kick for beats) -> noise. Delay 0-3 cooks of camera-monitor latency. | crutchfield spiral, infinite hall, cells, flame, kaleido moire |
| `modulate` (lane C, 27 Oct; FX7a SX-12) | in1 + b_src (in1 / b_sel = Btop / b_noise) -> fx -> out_sel | The Hydra modulate bank (maths re-written; hydra-synth is AGPL, read for the list only): B, read at the same uv, bends where A is read. Modes: modulate (uv + (B.rg - Offset) x Multiple), scale (1 / (1 + Offset + Multiple B.r) about the centre), rotate (Offset + Multiple B.r rad), hue (uv + (B.g - B.r, B.b - B.g) x Multiple px), pixelate (cells Offset + Multiple B.rg), repeat (Repeatx / y tiles, odd rows / columns shifted, + B.rg x Multiple), kaleid (Sides fold, radius x (1 + Multiple B.r)), scroll x / y (+ Multiple B.r + Speed t). Amount mixes the uv; Wrap repeat / mirror / hold / transparent. B = A itself (Hydra `src(o0).modulate(o0)`), any TOP, or moving colour noise (1/4 res). Chain with vfeedback in the rack for feedback tunnels. | self warp, noise ripple, luma twist, pixel bloom, kaleid breath |

Notes:
- `vfeedback` is not FX_glitch `feedbackkill`. That module models generation loss (crush, burn-in, photocopy); this
  one is the studio optical loop. They share no code. Each has its own small stamp.
- `scanimate`: use it on titles typed into `Text` (whole words, never split) and land them clean with Settle 1; keep
  brand logos undistorted. Default palette is `sunset`; the old `prism` palette is now `gold` (user 26 Oct: PRISM is
  no longer relevant).
- `ruttetra` vs td-port `rutt_lines`: the td-port module is a per-pixel ribbon search with no TD verification, and it
  was read only as an idea source. Here the geometry is real: the GPU displaces the vertices (the v002 / derivative
  forum route), so the cost is per vertex, not per pixel x line.

## LIVE CHECKS (TD 2025.31550; scratch or b2 first for ruttetra and the two feedback modules, then main)
Reads go in separate execs, >= 3 frames after a change (`# allow-readback`; T-111 (4), T-116 (4)). Pane elsewhere for
cost and restart checks (T-122 (4)). Register the lane (`tools/lane.py add FX_synth`), checkpoint after every verified
step, then save, park and bring home (T-120).

Test pictures. `ramp`: Ramp TOP, horizontal, black -> white, 1080x1920, **rgba32float**. 8-bit steps would break
the contour gradients. `grey`: Constant TOP 0.5, 1080x1920. Otherwise the stored clip. Wire each into FX_synth `in1`.

1. **Build clean** (all 6 added): `td_errors` none. Every compute DAT and the MAT compile. `post`, `look`, `trail`
   and `loop` are 16-bit float, and `stamp` is 1x1 32f. Record the real par names if one differs: Grid SOP
   `rows/cols/orient`, Geometry `instancecountmode manual`, Render `cullface`, GLSL MAT `sampler0extendu`, Cache TOP
   `cachesize/outputindex/active`, Text TOP `fontsizex`. The builder skips missing names (`_set` / getattr guards),
   so check by hand that each one took effect.
2. **Exact passthrough, every module** (clip paused): Amount 0, slot enabled 0, mix 0, Panic -> numpy max diff
   **0** vs `img_src`. A module tile with Amount 0 shows no fx cook (`out_sel` = 0).
3. **colorize**
   - Identity (Source rgb, Function ramp, Gains 1, Phases 0, Clip, Drive 1) on the clip: max diff <= **1/255**.
   - `ramp` + paik phase preset (Gains 1.5): out1 vs `fx_synth_logic.colorize(in, preset)` max <= **2/255**.
     Spot values (x = column): x 270 -> (0.855, 0.637, 0.021); x 540 -> (0.498, 0.063, 0.939); x 810 -> (0.148,
     0.981, 0.358).
   - Solarize T 0.55 Drive 1.4: no value above 0.55 + 1/255.
4. **bands**
   - `ramp`, Fill grey, Bands 8: exactly **8** distinct levels 0.0625 ... 0.9375 (+- 1/255).
   - `ramp`, Bands 10, Fillamt 0, Background black, Linewidth 2, white: **18** lit columns (> 0.5), at **107/108,
     215/216, 323/324 ...** (= 108k - 1, 108k).
   - Speed 0.5 on the clip: contours move, and two reads 0.5 s apart differ; Speed 0 reads are identical.
   - Cost <= **0.3 ms**.
5. **keyer**
   - `ramp`, Keya luma, Low 0.5, Soft 0, Op matte: columns < 540 = 0, >= 540 = 1 (the boundary column is +-1).
   - Iris (Keya shape, circle, Position 0.45, Soft 0, matte) on the 1080x1920 frame: key mean **0.372 +- 0.005**
     (R = 495.7 px from the centre).
   - Op xor bits: Constant 128/255 A, B colour 64/255 -> out1 = **192** in 8-bit.
   - Green screen: a Constant (0,1,0) region -> key 0 (shows B), and the clip's skin keeps key 1.
   - Btop = another TOP path, Bsource top: B follows it, fitted to in1's size.
6. **ruttetra** (scratch first: a new GLSL MAT + Render path in a rack)
   - `grey`, Lines 64, Defy 0, Width 1, Glow 0, Colour mono white (Monor/g/b 1), Background black: lit rows centred
     at **y = 15 + 30 i** (64 lines, texel y from the bottom), nothing between them. If the image is upside down or
     rows sit at H - y, record it (Render NDC vs texel y) and flip the vertex shader's y.
   - Same picture with Defy 0.1: every line moves up by **96 px** (0.1 x 0.5 luma x 1920).
   - Scan vertical: 64 columns at **x = 8.4375 + 16.875 i**.
   - Rotate 90: the lines turn vertical about the centre.
   - Classic relief preset on the clip: bright areas lift. Capture it.
   - Cost at 96 x 256 (default) and 256 x 1024: render GPU + post. Target <= **2 ms** at the default (the vertex
     count is 49k / 524k). Note the 512 x 1024 worst case.
   - Persist 0.6: an old beam fades by 0.6 per cook (two reads: decayed rows ~ 0.6^n).
7. **scanimate**
   - Settle 1, Zoom 1, Rotate 0, Key 0, Keysoft 0, Source input, Decay 0, Glow 0, Lines 0, Palette mono, Colour logo,
     Background black: out1 = the clip within **2/255** (the warp is the identity at texel centres).
   - Text source, flying logo preset: trails visible, alpha (age) in `trail` falls by Decay per cook. Two reads n cooks
     apart: an untouched trail texel ratio = **0.93^n +- 2 %**.
   - Settle 0 -> 1 over 2 s: it lands on the whole, unbroken text.
   - Bypass the slot for 1 s and re-enable (pane elsewhere): the first read has no old trail (stamp z small).
   - Text TOP `fontsizex` units: is the size `Textsize` x width? Record what it is.
   - Cost: warp + trail + look <= **1.5 ms**. Mipmapping the `look` inputs also mips in1; record the extra.
8. **vfeedback**
   - Identity (Inject 0, Zoom 1, Rotate 0, Blur 0, Contrast 1, Huestep 0, Autogain 0): two reads of `loop` apart are
     identical (max **0**), while in1 changes.
   - Shift x 1, Edge repeat: `B == np.roll(A, zB - zA, axis=1)` exactly (stamp z counts the cooks).
   - Huestep 120: three generations return the start picture (<= 2/255 at 16f).
   - Autogain 1, Target 0.45, `grey`-like constant 0.05 live, Inject 0: after 2 s the mean luma of `loop` is
     **0.45 +- 0.02**, and stamp w matches the numpy 64x64-grid mean within 0.01.
   - Delay 2: the loop reads 2 cooks back (Shift x 1 per cook -> the step per loop doubles in time). Record the Cache
     TOP index sign.
   - Presets 1-5, 30 s each on the clip: mean luma in **[0.03, 0.97]**, std > 0.01, no NaN. Offline, 120 generations
     of every preset already pass this.
   - Cost: loop <= **1.0 ms** (6 bilinear taps), stamp + mix ~0.1 ms.
9. **Rack**: all six on at once on the clip, pane elsewhere: project fps (target 60, `cookRate` untouched) + per-module
   ms. Then presets recall, one capture per module, `td_checkpoint`, save, park, results here + a T-entry.

**modulate LIVE CHECKS (lane C; scratch, then main by builder):** M1 `add` modulate: errors 0, `b_noise` pars took
(period, tz, mono), `b_src` follows Bsource. M2 Amount 0 -> out1 = in1 (max 0). M3 parity: test clip in, each of the 9
modes (Bsource self, Wrap mirror, preset-like Multiple), frozen clip: out1 vs `fx_synth_logic.modulate(in1)` within
2/255 on >= 99 % of pixels (pixelate / repeat cell edges and wrap seams may flip). M4 constant B (Btop = a Constant
0.75 / 0.5), modulate Multiple 0.2 Offset 0.5: out1 = in1 shifted 0.05 of the width. M5 presets 1-5 recall full
state + one capture. M6 cost: fx GPU median at 1080 x 1920 (estimate 0.15-0.35 ms) + noise source.

**modulate verified live (scratch TD, 2025.31550, 27 Oct; main's FX_synth loaded read-only, `add` modulate):**
M1 errors 0; b_noise 270 x 480 (1/4), period / tz expressions set, `b_src` follows Bsource. **Bug fixed live:** the
fx pass used the GLSL TOP's default `inputextenduv` zero, so uv ~1 (mirror / repeat edges) read half-transparent
(0.2 % of pixels off by up to 0.66); the module now sets extend hold (T-119 (4) again). M3 parity after the fix
(static rgba32f colour noise in, 1080 x 1920, every mode, Wrap mirror and repeat): out1 = `modulate()` within 2/255 on
**100 %** of pixels, max 1e-4 for 8 modes; pixelate max 0.29 on a few cell-edge texels (p99.9 0). M2 Amount 0: max
**0** (out_sel 0). M4 Btop = Constant (0.75, 0.5), Multiple 0.2, Offset 0.5: out1 = in1 shifted 54 px exactly (max
**0**). M5 presets 1-5 recall their full state (0 mismatches); capture
`output/fx_synth_modulate2_noise_ripple.png`. M6 cost (noise ripple, pulled 150 frames): fx **0.26 ms GPU** + 0.10
CPU, b_noise 0.57 GPU + 0.13 CPU, module total 1.5 ms median, pull fps 58.9.

**modulate in main (lane C, 27 Oct, by builder):** `add(FX_synth, 'modulate', enabled=0)` in main: modulate1 slot 7,
errors 0, fx extend hold, 2059 ops; forced cook vs `modulate()` on the live in1: within 2/255 on 100 %, max 0.0027;
parked, **main saved `JazibTD_home.576.toe`**.

Library `FX_synth` 0.2.0 (with modulate1, 27 Oct).

## Not done / open
- AV-21 `osc` (oscillators / shapes), AV-25 `vfilter`, AV-29 `magnet` and G-HOLO are listed for FX_synth in FX0 but
  were not part of this job. The keyer's shape generator covers the key-generator part of AV-21.
- No AV-20 signal bus (shared A-F buses, cross-modulation). The rack is a serial chain like FX_glitch, and keyer B
  (Btop) is the only second input. Build a bus only when 2+ modules need cross-patching (no-bloat rule).
- ruttetra persistence has no stamp: after a bypass, an old phosphor frame fades out over a few cooks (Persist^n)
  instead of restarting.
- ruttetra hidden lines are not removed (wireframe, like the analog original).
- Audio: bind `Kick` (vfeedback), `Speed` / `Wobble` (bands), `Wave` (ruttetra) or `Fly` (scanimate) to a CHOP. There is
  no built-in audio input.

## Verified live (26 Oct 2026, TD 2025.31550)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Main TD for colorize / bands / keyer and the final rack; scratch TD first for ruttetra, scanimate and vfeedback
(copy under `/project1/synth_lane`, removed after). Test pictures in a temporary `FX_synth_test` COMP (ramp 32f,
constant, the stored clip), removed after. The main TD ran at ~20 fps the whole time (other lanes' COMPs cooking:
PX_pointfx, GEN_sim, FX_scope), so fps numbers are deltas, not a 60 fps proof.

1. **Build clean:** td_errors none for the rack and all six. Pars took effect: Grid SOP `orient xy`, `rows 2`, `cols`
   = Samples; Geometry `instancing`, `instancecountmode manual`, `numinstances` = Lines; Render `cullface neither`,
   rgba16float, `antialias aa1`; GLSL MAT `sampler0extendu/v hold`, blending one/one, depth test off; `post` 16f.
   Cache TOP `cachesize 4`, `outputindex -2` at Delay 2 (negative = older), `active`. Text TOP `fontsizex` is in
   points (`fontsizexunit points`): 172.8 = 0.16 x 1080.
2. **Exact passthrough** (clip paused, img_src vs out1, all six slots at once): Amount 0 -> max diff **0**, slot
   enabled 0 -> **0**, mix 0 -> **0**, Panic -> **0**; every module's `out_sel` 0 at Amount 0. Control: all six on
   (preset 1) -> max 1.0.
3. **colorize:** identity on the clip **0** (better than 1/255); paik phase on the ramp: spot values x 270 (0.855,
   0.637, 0.020), x 540 (0.498, 0.063, 0.939), x 810 (0.148, 0.981, 0.358); vs `fx_synth_logic.colorize` max
   **1.5e-4/255** on a full row; solarize preset max **0.549** (<= 0.554). Cost 0.74 ms median (fx GPU 0.16).
4. **bands:** Fill grey Bands 8 -> exactly 8 levels 0.0625 ... 0.9375. Bands 10 lines: the 18 interior columns at
   107/108, 215/216 ... 971/972 as planned, **plus** columns 0 and 1079 at coverage 0.500 / 0.4997 (the thresholds 0
   and 1 at the frame edge; the edge-clamped gradient halves g, so the numpy reference also gives exactly 0.5 there).
   Speed 0.5: two reads 6 s apart differ (max 0.83, 25 % of px); Speed 0: identical (max 0). Cost 0.82 ms median, fx
   GPU **0.21** (the 0.3 ms target was GPU).
5. **keyer:** luma matte on the ramp: columns <= 539 = 0, >= 540 = 1 (row-exact); iris 0.45: key mean **0.3722**,
   max lit radius 495.65 px; xor bits 128 ^ 64 = **192**; green screen: Constant (0,1,0) -> key 0, clip skin pixels
   (29 % of the frame) key 1.0. **Bug fixed live:** B through a Fit TOP had its border at 0.75x (Fit blends the
   edge with bgcolor, T-128 (2)); `b_fit` is now a Transform TOP (fill outside, extend hold): a 540x960 ramp as Btop
   -> out1 = the fitted ramp within 0.49/255, edges included. Cost 1.5 ms median (window x diamond; fx GPU 0.34).
6. **ruttetra** (scratch): grey, Lines 64, Defy 0, Width 1: 64 lit rows, intensity-weighted centres at texel
   14.5 + 30 i (= y 15 + 30 i, no flip needed); Defy 0.1: every line up by **96.37** px (0.1 x 128/255 x 1920 = 96.38);
   Scan vertical: 64 columns, centres within **0.0015** px of 8.4375 + 16.875 i; Rotate 90: vertical lines at
   x = 15 + 30 i (symmetric about 540, 36 in frame); Persist 0.6: an old beam reads 0.2998 (= 0.6 x 0.4997) one cook
   after the move, then ratio 0.01005 = 0.6^9.0. Classic relief capture:
   `output/project1_lab_FX_synth_out1_2026-10-26T16-24-09-494Z.png`. Cost (scratch, Wave on so it renders every
   frame): GPU render 0.84 + post 0.40 + outc 0.24 ms at 96 x 256; render GPU 2.1 at 256 x 1024, 2.5 at 512 x 1024.
   The Render TOP's CPU side is ~1.7 ms on top (Rosetta floor, T-112), so the module is ~3.3 ms at the default, over
   the 2 ms target; open item.
7. **scanimate** (scratch): Settle 1 identity (input source, Key 0, Decay 0, Glow 0, mono, logo colour) -> max diff
   **0** vs the clip. Trail age falls by Decay per cook: one cook after the text moved, the old texels read 0.9297
   (0.93 in 16f). Restart: a 0.6 s unpulled gap reset stamp z (891 -> 7), so no stale trail. Cost 1.49 ms median
   (banded streamers; look GPU 0.35); on main alone 3.1 ms median (trail GPU 0.88, look 0.32, in1 mip 0.15).
8. **vfeedback** (scratch): **bug fixed live:** the identity loop drifted (9.5 % of texels, up to 0.005 over 11
   generations) because the sampler's bilinear is not exact (T-128 (1)); `tap()` is now a float32 bilinear from 4
   texelFetches. After it: identity two reads 12 cooks apart, max **0** while in1 changed (0.89); Shift x 1 Edge
   repeat: B == np.roll(A, zB - zA = 11) exactly; Huestep 120: 6 generations apart max **0.75/255**; Autogain 1
   Target 0.45 on a 0.05 constant: loop mean luma **0.4505**, stamp w 0.44987 = numpy 64x64 grid mean (diff < 1e-7);
   Delay 2: B = roll(A, 4) over 9 cooks (one step per 2 cooks); presets 1-5, ~9 s each on the playing clip: mean
   luma 0.387 / 0.463 / 0.057 / 0.652 / 0.315, std 0.20-0.27, no NaN. Cost 1.87 ms median (loop GPU 0.57).
9. **Rack:** all six on (preset 1) on the clip, pane off the COMP, pull-only: median frame 50.0 ms vs 46.5 ms with
   Panic on, i.e. **~3.5 ms per frame for all six** on a TD that was at ~20 fps from other lanes. Per-op GPU numbers
   inside the full chain are attributed to the waiting op (scanimate in1 6.2 ms in the chain, 0.15 alone; T-128 (4)).
   Slots left enabled 0, module pars at preset 1, COMP parked, project saved.

**Perf pass (26 Oct, 2025.31550, b5, perf lane):** ruttetra preset 1 (classic relief, Lines 120 x Samples 256, test
clip, out1 pulled each frame, per-op cpu + gpu of the ops cooked that frame, 90-110 frames, 5 runs): **total
3.0-3.8 ms** = render CPU 1.1-1.6 + render GPU 0.7-0.8 + post 0.4 + outc 0.2 + in1 / mat / fb ~0.2. The Render TOP
CPU does not follow the work: Lines 16 x Samples 64 = 1.35 ms, Lines 120 x 256 = 1.25 in the same minute (fixed
per-render cost under Rosetta, T-112 (3)). Tried, no measurable change, nothing kept: the MAT's 26
`parent().par.X.eval()` uniform expressions as `parent().par.X` (render CPU 1.10 / 1.34 vs 1.11 / 1.46 interleaved) or
as constants; post without mips (glow mips cost ~0). A paired copy of the render chain is not comparable (an
unwired Render TOP copy cost 0.65-0.8 CPU / 0.4 GPU in A/A, LEARNINGS T-145). Only removing the Render TOP (a compute
line rasteriser) would get it under 3 ms; not done (additive overlapping beams need atomics or a gather pass, a
rewrite with its own parity work).

Open: ruttetra over the 3 ms budget (Render TOP CPU floor); a fair 60 fps check needs a quiet TD; scanimate Settle
0 -> 1 landing and the bypass-restart read were not checked by capture.

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.748).
