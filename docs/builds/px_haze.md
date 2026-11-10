# px_haze - volumetric haze, light shafts and bloom v2 (lane W1-D, 27 Oct 2026)

User (27 Oct): "volumetric haze nd glow and all", colours changeable, lights placed in 3D affect the scene.
RUBENFRO_COVERAGE rows H1 (depth haze, height falloff, drift), H2 (light shafts), H3 (fog lit around lights), GL1
(bloom: two scales + tint), CO5 (tints). TD target 2025.31550. Phase 1 offline (logic, numpy references, tests,
glslc); **phase 2 live on b5 (27 Oct): every check passed, GPU = numpy reference within float16 (section "Verified
live")**; FX_haze brought home to main /project1/lab/FX_haze (parked).

## Files (all new; px_glow.glsl / px_post.glsl untouched)
| File | What |
|---|---|
| `builders/glsl/px_haze.glsl` | haze pass: ONE compute at quarter (default) or half res: height fog + fbm drift, in-scatter of up to 8 lights, screen-space shafts |
| `builders/glsl/px_haze_comp.glsl` | composite: haze over the scene (`pxhApply`, foldable into px_post) |
| `builders/glsl/px_bloom.glsl` | bloom v2: drop-in for px_glow (same `uB`), + tight scale, ring halo, palette tint, knee, firefly clamp |
| `builders/px_haze_logic.py` | pure: uniform rows, camera basis (look-at / TD Camera COMP / PX camera), light rows, W1-A light-block adapter, colour source (W1-B), numpy mirrors of all 3 shaders, closed forms, cost model, `shader_text()` (prepends `px_palette.glsl`) |
| `builders/px_haze.py` | standalone builder: COMP `FX_haze` over ANY TOP (+ depth), lit by TD Light COMPs; the live harness |
| `test/test_px_haze.py` | 29 offline tests: `python3 -I -m unittest discover -s test -p 'test_px_haze.py'` (~1 s) |

## Haze pass (`px_haze.glsl`)
Inputs (exactly 2 wired, T-84 / T-88): **0** = scene RGBA premultiplied, any res (wire a half-res mipmap copy: alpha is
the occluder); **1** = depth (r), or a 1x1 Constant when there is none (Depthmode `none`). Output rgba16float at the
TOP's resolution (half of the output): rgb = light the haze adds, a = 1 - transmittance.
Composite: `out.rgb = src.rgb * (1 - a) + rgb`, `out.a = src.a * (1 - a) + a` (empty pixels take the haze).

Uniforms (Arrays page, vec4 uniformarray from Script CHOPs; Vectors page for the rest):
| Uniform | Rows | Content |
|---|---|---|
| `uH[13]` | `haze_rows(params, cam, nlights)` | 0 cam pos, tan(fovx/2) / 1 right, aspect at pack (unused: the shader uses its own output aspect, so the rows never read a TOP size) / 2 up, near / 3 fwd, far / 4 Hazecol, density / 5 floor y, falloff, noise, noise scale / 6 wind xyz, extinction / 7 lit tint, gain / 8 g, ambient, steps, light size / 9 shafts, decay, length, taps / 10 threshold, disc, occlusion, light count / 11 depth mode, depth scale, objdist, maxdist / 12 noise per sample, jitter, shaft mip lod |
| `uHL[40]` | `light_rows(lights)` | 5 rows per light (max 8): pos, type (0 point 1 spot 2 area 3 directional) / axis, range / colour, shaft weight / cos outer, cos inner, half w, half h / intensity, area U axis |
| `uHt` | TOP expressions | x `absTime.seconds` (noise drift), y `absTime.frame % 65536` (jitter): uH stays static (T-143) |
| `uHazeCs` | `haze_cs()` / colsrc pars | W1-B colour source (mode, pos, spread, keep) |
| `uPal[16]`, `uPalCtl` | W1-B `pal_rows` / `pal_ctl` | shared palette (prepended `px_palette.glsl`) |

Maths:
* **Density** sigma(p) = Density x exp(-Falloff x max(y - Floor, 0)) x noise, noise = max(1 + N (2 fbm - 1), 0), fbm =
  3 octaves of value noise at (p - Wind t) x Noisescale (drifts with the wind).
* **Transmittance**: closed-form optical depth of the height fog along the ray (piecewise at the floor; the UE /
  Quilez exponential height fog integral), x the noise at the ray middle; T = exp(-Extinction x tau). Extinction 0 =
  light-only haze (the scene is not dimmed).
* **Ambient haze** = colour x Ambient x integral(sigma T dt) = (1 - T) / Extinction (exact for this fog).
* **In-scatter** per point / spot / area light: equiangular sampling (Kulla & Fajardo 2012) on the light's closest
  point, with a smoothstep warp of the angle (dense samples at both ends where T moves fast) and exact weight
  normalisation; intensity / (d^2 + Lightsize^2) (finite through the light), Henyey-Greenstein phase normalised so
  isotropic = 1, spot = smoothstep(cos outer, cos inner) (TD convention: full beam inside cone/2, 0 at cone/2 + delta),
  area = nearest point of the rectangle, one-sided (normal = axis), range = smooth window (1 - (d/r)^4)^2 and the
  march clipped to the range sphere. Directional = colour x phase x (1 - T) / Extinction (no shadow).
* **Shafts** (Mitchell, GPU Gems 3 ch. 13): per light on screen, `Taps` taps from the pixel toward the light's screen
  position over `Length` of the way, decay per tap; source = a soft disc of radius `Disc` (screen-height units, aspect
  corrected) around the light + pixels above `Threshold`; blocked by scene alpha x `Occlusion` and (with depth) by
  anything nearer than the light (one compare per tap in the depth input's own units). Lights behind the camera give
  no shafts. Taps start at a per-pixel interleaved-gradient-noise offset (fixed taps drew stair bands, live b5) and
  read mip `Shaftlod` of the inputs (haze TOP input filter mipmap; 1 = default, cache-friendly). Shafts also add over
  occluders (light in the air in front of them), as in Mitchell's method.
* **March end**: depth (view z / NDC 0..1 / ray distance; far = sky = Maxdist) or, without depth, Maxdist blended to
  Objdist by the scene alpha (covered pixels get the fog in front of them only).
* **Colour**: each light's fog colour = `pxColSrc(uHazeCs, Hazecol, light colour, k)` x intensity (default mode
  `source` = the light's own colour; `solid` = Hazecol for all lights; `index` = light k gets palette stop k, beat
  drives step them); ambient = `pxColSrc(uHazeCs, Hazecol, Hazecol, march end / Maxdist)` (`attr` = colour by
  distance). Lit fog x `Hazetint` x `Gain`.

## Lights
* Standalone: `FX_haze` par `Lights` = Light COMP paths / patterns (TD `lighttype` point / cone / distant -> point /
  spot / directional; `cr cg cb`, `dimmer`, `coneangle`, `conedelta`, `attenuated` + `attenuationend` = range; area
  from W1-A only); `Camera` = a Camera COMP (or the manual Campos / Camtarget / Fov). Rows re-cook per frame (Frame
  clock) so moving lights / camera follow.
* PX / effectors (W1-A, `docs/builds/effectors.md` "Lights", landing): `lights_from_block(blocks)` turns W1-A's 7-texel
  light blocks (colour + intensity, position + type, forward, attenuation, cone cosines, area half-U / half-V) into
  `light_rows` input, exact cone cosines and area axes kept. The wave-2 PX owner calls it with the same numpy block
  the buffer is packed from; the haze shader needs no buffer input (inputs stay at 2).

## Bloom v2 (`px_bloom.glsl`, replaces px_glow in wave 2)
Inputs: **0** = 1/8 mipmap (PX's `glow_in`, wide), **1** = 1/4 mipmap (tight; in legacy use, wire glow_in again).
Output = the TOP's res (1/4 for two scales; 1/8 = legacy), alpha 0 (px_post raises alpha from the glow).
| Uniform | x | y | z | w |
|---|---|---|---|---|
| `uB` (= px_glow) | threshold | intensity | wide tap spacing | soft knee (0 = hard, legacy) |
| `uB2` | wide weight (1) | tight weight (0 = one scale, input 1 not read) | tight tap spacing | firefly clamp (0 off) |
| `uBt` | Bloomcol r | g | b (solid tint, white = legacy) | saturation (1) |
| `uBr` | ring amount (0 off) | ring radius (screen-height fraction) | width (0 tight .. 1 wide source) | chroma (r/g/b radius spread: rainbow ring); 16 taps from a per-pixel start angle (12 fixed taps drew beads, live b5) |
| `uGlowCs` | W1-B colour source: tint = `pxColSrc(uGlowCs, Bloomcol, white, 0)`; mode solid + white = today's glow | | | |
**Splat-aware**: thresholds the premultiplied rgb the splat render writes; knee + firefly clamp keep lone hot splats
from flickering the glow. Legacy settings take px_glow's exact loop (same tap order); tint / saturation are skipped
when they are identity, so the numbers match (offline: `array_equal`; GPU diff 0 = LIVE CHECK G-a).

## Wiring
Standalone (`build('/project1/lab', 'FX_haze')`): in1 -> haze_src (Resolution quarter (default) / half, mipmap) -> haze (in 0,
in2 depth -> in 1) -> comp (in1 + haze) -> glow_q (1/4) + glow_e (1/8) -> bloom -> glow_add (Composite add) ->
sw_bloom (Bloom 0 = comp) -> out1. Script CHOPs haze_rows / light_rows / pal_chop are event-driven: the par and
Light / Camera COMP transform reads in their cooks are TD dependencies (live b5: 1 cook per change, 0 per static
frame; a per-frame clock had cost 0.65 + 0.25 ms CPU every frame);
Text DATs px_haze_logic, palette_map_logic, haze_rt.
PX wave 2 (PX owner): haze after `sw_trail` and before post (haze_src = a half-res Resolution of sw_trail; depth: PX
has no depth output today, so Depthmode none + alpha; W1-E geometry depth later); fold `pxhApply` into px_post (its
input 2 is free) to save the composite op; swap px_glow.glsl for px_bloom.glsl (bloom TOP res = Resx/4 x Resy/4 from
the PARS, T-143 (3)); camera = `camera_from_px(eng cam row, fov, Resx, Resy)`.

## Verified offline (27 Oct 2026, this Mac, numpy float64 + Homebrew glslc)
| Check | Result |
|---|---|
| in-scatter vs the closed-form airlight (point light, homogeneous, no extinction, isotropic) | exact (< 1e-9) for 1..32 steps; closed form vs a 400k-step brute integral 1e-4 |
| in-scatter, dense fog (tau ~2.4 to the light) + height falloff + g 0.4, 3 rays | error 8 steps 0.3-4.4 %, 10: 0.04-3 %, 16: 0.4-1.6 %, 32: 0.2-0.4 % (tests: < 3 % at 16, < 1 % at 32) |
| default look values (density 0.08, falloff 0.35, g 0.35, 8 steps) | 0.89 % vs brute (10 steps 0.55 %, 6 steps 1.7 %) |
| spot (cone 40 / delta 10) 32 steps vs brute | < 5 %; pointing away = 0 |
| range window, area one-sided, directional (1 - T)/ext vs numeric | ray outside range = 0, inside < 1 % at 32; area facing away = 0; directional 1e-4 |
| optical depth closed form vs numeric | < 1e-5 (rising, falling, below floor, horizontal, near-horizontal, no falloff) |
| noise | 0 = factor 1 exactly; drift = moving with the wind (1e-9) |
| shafts direction | an occluder inside the light's disc darkens the pixels beyond it on the light -> occluder line (< 0.6 x unoccluded, and further out < 0.8 x), the same distance 90 degrees off is unchanged (> 0.95 x); light behind the camera = 0 |
| projection | light screen position = PX `cam_viewproj` projection (1e-9); TD-style world matrix = look-at basis |
| off = identical | composite Amount 0 and an all-zero haze return the source exactly; haze with density / shafts / ambient 0 = 0 |
| colour | default cs = each light's colour; solid = Hazecol; index = palette stop k; W1-A block adapter keeps cone cosines + area axis |
| bloom | legacy rows == px_glow mirror (`array_equal`); tint (1, 0, 0.5) = channel gains; palette tint = `pal_eval` colour; saturation 0 = grey; two scales linear; knee finite; clamp cuts a 50x hot pixel's glow > 10x; ring peak radius 0.2 +- 0.02 |
| glslc | px_haze (+ px_palette), px_haze_comp, px_bloom (+ px_palette) compile; max input index 1 |
| builder on fake TD | 3 GLSL TOPs, <= 2 wired each, every declared uniform bound (arrays from existing CHOPs), every `parent().par.X` exists, idempotent rebuild, Frame clocks on haze_rows / light_rows only |

## Cost (measured live, b5, 31550, 27 Oct; 5 TDs open, 2 other lanes building on the same GPU)
| Case (1080 x 1920 in, 4 lights: point, spot, 2 point; viewz depth) | GPU / CPU ms |
|---|---|
| **haze, defaults (quarter res 270 x 480, 8 steps, 12 taps, noise, shafts)** | **0.46 / 0.20** |
| haze at half res (540 x 960) | 2.2-3.2 / 0.2 (shafts ~60 %; noise ~0; depth taps ~0.5) |
| haze with no lights (ambient fog only) | 0.17 |
| whole FX_haze (haze_src 0.35, in2 depth 0.27, haze, comp 0.15, bloom 0.18, glow_add 0.09, rest) | 2.2 total; rows 0 per static frame |
| bloom v2 two scales (1/4 output) | 0.18 (px_glow alone measured 0.4-0.6 in PX: no regression) |
| real fps of b5 with the full chain pulled every frame at 1080 x 1920 | 60.8 (cookRate 60) |
`haze_cost_ms` is fitted to these numbers. Levers: Hazeres (half = ~4x), Shafts 0, Taps, Steps, Shaftlod, fewer
lights. Single-run medians swing ~1.5x on this shared GPU (T-145); the quarter-res default is well inside 0.8 ms.

## Verified live (b5, 2025.31550, 27 Oct 2026; harness /project1/lab/hz_test on b5: sphere + floor, Render TOP, Depth TOP, 4 Light COMPs, a copy of BL_splat_render)
| # | Result |
|---|---|
| H-a | build clean, 0 errors on every op, all three shaders (palette include) compile; first GPU run at 270 x 480 / quarter res / 4 steps / 8 taps, raised to 1080 x 1920 after clean frames |
| H-b | uH 13 / uHL 40 / uPal 16 samples; the rows read back from the CHOPs fed to the numpy reference reproduce the GPU (below) |
| H-c | one point light, Density 0.1, no extinction, isotropic, 8 steps: GPU / closed-form airlight -0.02 .. -0.08 % at 5 pixels (rgba16float); whole image GPU vs `ref_haze` median 0.03 %, p99 0.09 % |
| full pass | 3-4 lights incl. spot, shafts with threshold, Depthmode none / viewz / ndc: GPU vs `ref_haze` median 0.03 %, p99 0.09 % (alpha 5e-4); noise on: means within 1 % (the value-noise hash differs float32 vs float64 at a few cells, p99 4-12 %) |
| H-d | occluder in front of a light: shafts behind it on the light -> occluder line 0.39 vs 2.45-2.48 at the same distance 90 degrees off (6x darker); captures `output/px_haze/h2_shafts_only.png`, `h3_shaft_streak.png` |
| H-e | Hazeamount 0 + Bloom 0: out1 == in1, max diff 0 |
| H-f | Light COMP on 31550: `lighttype` point / cone / distant (no area: W1-A packs area itself), `cr cg cb`, `dimmer`, `coneangle`, `conedelta`, `coneroll`, `attenuated`, `attenuationstart / end / exp`; Camera `fov` (horizontal; no fovaxis par), `near`, `far`. Moving / recolouring a light updates light_rows in the next cook |
| H-g | Depth TOP takes the Render TOP in its `op` par (no input wire); `depthspace` cameraspace = positive view z (sky = 1000.24 with far 1000) -> Depthmode viewz; input = 0..1 (sky 1.0) -> Depthmode ndc; both give the same haze (means within 0.1 %) |
| G-a | px_bloom with legacy rows vs px_glow on the same 1/8 input: max diff **0**, 0 texels differ |
| G-b | splat render (copy of BL_splat_render, SmileyPinata 228 287 splats, 540 x 960): two-scale + palette tint (neon_trio pos 0.3) + ring, 0 errors (`g1_splat_bloom_ring_palette.png`); orbiting 30 deg/s, bloom energy changes smoothly frame to frame (no spikes); firefly clamp has no effect on this LDR scan (excess luma < 1) |
| ring | 16 taps + per-pixel start angle: smooth rainbow ring (`g2_ring_halo.png`) |
| P-a | table above: haze 0.46 ms at the default quarter res (target 0.8 ms met), half res 2.2-3.2 ms (not met: use quarter, or half with Shafts 0 ~1.2 ms) |

Fixes from the live run (all in the committed files): Light COMP `render` flag reads False (no enabled filter);
Composite TOP `useinput` took the bloom's 1/4 size (custom size = comp); shaft stair bands (IGN offset); ring beads
(16 taps, IGN angle); per-frame row cooks (event-driven, aspect from the shader's own output size); shafts' depth test
(one compare per tap) + mip taps; one shared exp per in-scatter sample; defaults steps 8, taps 12, Hazeres quarter.

## LIVE CHECKS (run on b5 27 Oct, results above; rerun after shader changes)
| # | Check | Pass |
|---|---|---|
| H-a | build FX_haze, td_errors clean, compile log of haze / comp / bloom (palette include) | 0 errors |
| H-b | uniform arrays: uH 13 / uHL 40 / uPal 16 samples land in order (read back via a debug compute or `td_why`) | rows = haze_rows / light_rows |
| H-c | in-scatter vs closed form: 1 point light, Density 0.1, Falloff 0, Noise 0, Extinction 0, g 0, Shafts 0, Ambient 0, Steps 8; read 5 pixels' rgb | GPU / `airlight_point` < 1 % (float32) |
| H-d | shafts: one Light COMP + a sphere in front of it in in1 | dark streak points away from the light's screen position (capture) |
| H-e | off = identical: Hazeamount 0 and Bloom 0 | out1 == in1 (max diff 0) |
| H-f | Light COMP par names on 31550 (`lighttype` names, `coneangle`, `conedelta`, `attenuated`, `attenuationend`), Camera `fov` axis | rows follow the light when moved / recoloured; LEARNINGS if a name differs |
| H-g | depth: Render TOP depth via Depth TOP: which mode (view z / NDC) and sky value | fog stops at geometry; doc the mode |
| G-a | bloom legacy: px_bloom with legacy rows at 1/8 vs px_glow on the same glow_in | max diff 0 (else note the float diff) |
| G-b | two-scale + ring + palette tint on a splat render (BL_splat_render / truck.splat) | capture; no flicker with clamp 4 |
| P-a | cost with other COMPs parked: haze 4 lights half res, bloom v2 | <= 0.8 ms / +0.2 ms; real fps 60 |

## Open
* PX has no depth output: haze in PX uses alpha (objdist) until W1-E geometry / a depth pass exists.
* Shadows inside the in-scatter (light occluded by the scan) are not modelled; shafts give the occlusion look.
* The quarter-res bilinear composite can halo by ~2 px at silhouettes (half res ~1 px); a depth-aware upsample needs a low-res depth.
* `pal_count` (uPalCtl.x expression) re-runs palette_stops when the palette pars change (0.03 ms).

## In PX (wave 2, 27 Oct 2026; docs/builds/px.md "Wave 2")
PX_pointfx has both passes built in: Haze page (Vh* = the FX_haze pars, lights = a selection of the light effectors
`Vhlights`, packed W1-A blocks -> `light_rows` in px_rt) composited inside `px_post` (input 2, `uQh`), and px_bloom in
place of px_glow (legacy defaults = out1 diff 0 after splitting the legacy loop out, T-178 (1); this file's bloom
change is that split only). Live b5: haze GPU vs `ref_haze` median 0.033 %, p99 0.087 %; cost haze ~0.6 ms quarter res.
