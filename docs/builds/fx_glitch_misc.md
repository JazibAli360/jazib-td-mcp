# fx_glitch module `misc` (micro effects bank, FX0 row 82 / FX4 G-*) - offline prep, 26 Oct 2026

Status: **live on b3 + main (26 Oct, 31550), slot `misc1` (enabled 0).** Everything marked **LIVE CHECK** needs TD 2025.31550.
Rack + module template: `docs/builds/fx_glitch.md`. Research: `docs/research/FX4_software_fx_emulation.md` (G-BEND,
G-TRI, G-LONGSHADOW, G-ELECTRIFY, G-AUTOLEVEL, G-DISP, G-ZAP; Suckr), backlog `FX0_effects_backlog.md` row 82.

Files: `builders/fx_glitch_misc.py` (module), `builders/fx_glitch_misc_logic.py` (numpy reference of every type, same
hash and sampling as the shader; `reference`, `compare`, `ref_stats`, `zap_branches`), `test/test_fx_glitch_misc.py`
(28 tests: template contract, uniforms vs shader, full-state presets, glslc of `fx` + `stats`, exact uint hash,
per-type behaviour, region crop = full crop).

One module, not eight: the user's no-bloat rule. Each type is 20-60 lines of GLSL in one compute pass, chosen by the
`Type` menu, sharing a small par set. Add a second `misc` slot to stack two types.

## Network
`in1` -> `stats` (compute, 2x1 rgba32float in place, ONE 256-thread workgroup; works only while Type = autolevel,
`inputfiltertype` = mipmap only then) ; `map_none` (1x1) / `map_src` (Select: the Map TOP only while Type = displace
and Maptop is set) -> `fx` (one compute pass, `inputextenduv hold`, format useinput; inputs in1, stats, map_src = 3,
T-88) -> `out1`. Amount 0 = texelFetch of in1 (exact passthrough).

## Types
| Type | What | Pars used |
|---|---|---|
| bend (G-BEND) | morph each pixel's lookup from where it is to its polar place around the Point: angle -> x (seam at Angle), radius / Length -> y. Strength 0 = picture, 1 = full polar; values between bend the picture round the point ("bend over and relax") | Strength, Length, Angle, Point |
| suck (Suckr) | black hole at the Point: the picture at radius r comes from r (1 + Strength L / (r + L)) (pulled in; negative = pushed out), swirl Angle x exp(-r / L), event-horizon disc of Size px with Softness | Strength, Size, Angle, Length, Softness, Point |
| tri (G-TRI) | equilateral triangle lattice (Size px side, rotated by Angle about the centre); each triangle splits into 4 (Sierpinski midpoint subdivision) while its corner lumas differ from its centroid luma by > Detail, up to Levels (<= 4); fill = picture at the final centroid; Edges darkens 1.5 px along the edges | Size, Angle, Detail, Levels, Edges |
| longshadow (G-LONGSHADOW) | pixels with luma (x alpha) above Threshold (+-Softness) cast a shadow in direction Angle (0 = down, 90 = right) up to Length px: up to 32 bilinear taps, falloff Decay along it, shadow colour = Colour, opacity Strength; casters stay on top | Angle, Length, Threshold, Softness, Decay, Strength, Colour |
| electrify (G-ELECTRIFY) | Sobel luma edges (spacing Width px) read at a value-noise-jittered position (noise cell Size px, jitter Length px), above Threshold (+Softness) glow Colour x Glow x Strength, added; flicker and a new jitter field Rate times/s | Size, Length, Width, Threshold, Softness, Colour, Glow, Strength, Rate, Seed |
| autolevel (G-AUTOLEVEL) | `stats` reduces the input's mip Level (default 4 = 67 x 120 texels at 1080x1920) to per-channel min / max + mean luma, smoothed over Smooth s; fx maps lo -> 0, hi -> 1 per channel, or one range (Linked); Clip shrinks (+) or widens (-) the range | Level, Smooth, Linked, Clip |
| displace (G-DISP) | displace by the luma gradient (central differences at Size px) of the picture or the Map TOP (sampled by uv, any size), offset = gradient x Strength x Length px; Prism: R at (1 - Prism), G at 1, B at (1 + Prism) of the offset | Size, Strength, Length, Prism, Maptop |
| zap (G-ZAP) | lightning from Point to Point 2: perpendicular fbm offset (5 octaves, Jag x length, tapered to 0 at both ends), glow exp(-d / Width); Branches (<= 6) leave the main bolt at random places at 20-55 deg, 15-45 % of its length; flicker + a new bolt Rate times/s; added (Colour x Glow x Strength) | Point, Point 2, Jag, Branches, Width, Colour, Glow, Strength, Rate, Seed |

Pages: **Misc** (Amount, Type, Strength, Size, Angle, Length, Threshold, Softness, Decay, Width, Rate, Seed),
**Points** (Pointu/v, Point2u/v), **Colour** (Colr/g/b, Glow; the glitch rack's `_pars` has no RGB style, so three
Floats), **Tri** (Detail, Levels, Edges), **Levels** (Clip, Linked, Smooth, Level), **Displace** (Prism, Maptop),
**Zap** (Jag, Branches). Slider ranges only, no clamps (no limits rule). Rate 0 = frozen (electrify / zap static).

Presets (full state each, T-124 (1)): 1 black hole (suck), 2 long shadow (black, 135 deg, 300 px), 3 triangulate
(96 px, 3 levels), 4 electric (cyan edge glow, Rate 12), 5 zap (bottom to top, 4 branches, Rate 10). bend, autolevel
and displace have no preset slot (5 max); set Type and go.

## Skipped (and why)
- **sparkle (G-SPARKLE):** built as `GEN_points.sparkle` (live 26 Oct); a second copy here would be a fork.
- **Tao (G-TAO) and Mir (G-MIR):** 3D geometry generators (extrude along paths, displaced terrain meshes), not picture
  filters: they belong with `G-CLONE` (repeat along a path), `GEN_points.form` (displaced grids) or `GEN_sdf`.
- **heat (G-HEAT):** `FX_palette_map` thermal ramp.
- **smear / blow (G-SMEAR):** `FX_glitch.smear`.
- Infinite zoom: `GEN_pattern.infzoom`; kaleido: `GEN_pattern.kaleido2`.

## Cost estimate (1080x1920, GPU; to be measured)
bend / suck 1 bilinear tap: ~0.2 ms. tri <= 17 taps (4 levels x 4 + 1): 0.5-0.9 ms. longshadow <= 32 taps:
~1.5-2.4 ms at Length >= 192 (smear's 24 taps measured 1.77 ms GPU, so the cap is 32, not 48). electrify 8 taps +
2 noise: ~0.6 ms. autolevel: mip generation of in1 (~0.3-1.2 ms, T-151 (3)) + stats (1 workgroup, 8040 texels)
+ fx 1 fetch: ~0.5-1.3 ms. displace 7 taps: ~0.5 ms. zap: 1 + Branches bolts x 5 octaves (2 hashes each) + exp:
~0.6-1.2 ms at 6 branches. When Type != autolevel, `stats` dispatches one workgroup that returns at once.

## LIVE CHECKS (b3 first; numbers from numpy, `fx_glitch_misc_logic.py`)
Setup: `add('/project1/lab/FX_glitch', 'misc')` -> `misc1`; Input test, clip paused (`test_clip.par.play = False`),
each read >= 4 frames after the change, reads in a separate exec from changes (T-74).

1. **Builds clean:** `td_errors` none on `misc1` (fx + stats compile: `shared` arrays + barriers, `textureSize(.., L)`
   with a lod, uint hash).
2. **Exact passthrough:** Amount 0, slot enabled 0, slot mix 0, Panic -> max abs diff **0** (`img_src` vs `out1`).
3. **Parity per type** (Rate 0, the type's preset or defaults; Amount 1): read in1 + out1 of `misc1`, reference on a
   window (full-res numpy of the tap-heavy types takes 5-20 s on the TD thread, so crop):
   ```python
   ns = {}; exec(open('<repo>/builders/fx_glitch_misc_logic.py').read(), ns)
   m = op('/project1/lab/FX_glitch/misc1')
   img = m.op('in1').numpyArray().astype('float64'); out = m.op('out1').numpyArray().astype('float64')
   pars = {p.name: (p.menuIndex if p.isMenu else p.eval()) for p in m.customPars if p.style != 'TOP' and not p.isPulse}
   R = (400, 800, 256, 256)                                 # x0, y0, w, h (row 0 = bottom)
   st = m.op('stats').numpyArray()                          # autolevel only: texel 0 lo rgb, texel 1 hi rgb + mean
   stats = (st[0, 0, :3], st[0, 1, :3], st[0, 1, 3])
   ref = ns['reference'](img, pars, t=absTime.seconds, stats=stats, map_img=None, region=R)
   print(ns['compare'](out[R[1]:R[1]+R[3], R[0]:R[0]+R[2]], ref, tol=3/255))
   ```
   Pass: `within` >= 0.99 for bend / suck / longshadow / autolevel / displace / electrify / zap (8-bit output, GPU
   bilinear weights are 8-bit fixed point); tri >= 0.97 (lattice edges: a pixel on a triangle boundary can fall either
   side in float32). Also pick a window across the point for suck and zap (R around Point * size). Read `stats` in
   its own exec when Smooth > 0 (it changes every cook).
4. **Behaviour:** autolevel on a dim picture (Level / Exposure lowered upstream): out min per channel ~0, max ~1 (on
   the mip level's extremes, so a few full-res pixels clip); longshadow black: out <= in everywhere; zap / electrify:
   out >= in everywhere; displace on a Constant TOP input: diff 0; tri Levels 0: <= one colour per triangle.
5. **Presets:** zkit Recall 1-5 set Type and every par exactly (full state).
6. **Rate:** electrify / zap at Rate 10: two reads 0.5 s apart differ; Rate 0: identical.
7. **Cost** (out1 pulled per frame, cpu + gpu of the COMP's TOPs, median over 120 frames, test clip excluded): each
   type <= ~3 ms (longshadow Length 300 and zap 6 branches are the heavy ones); project 60 fps (onFrameStart counter,
   T-124 (4)); `stats` ~0 when Type != autolevel.

## Verified live (26 Oct, 31550; b3 then main)
- b3: `add` -> `misc1`, td_errors none (fx + stats compiled). Clip paused on a real frame (img mean 0.468).
- Exact passthrough: Amount 0 / slot enabled 0 / mix 0 / Panic -> max diff **0**.
- Parity per type (Rate 0, Smooth 0, defaults; 256 x 256 window at (400, 800), zap at (412, 1300) on the bolt),
  `within` (3/255) / max: bend 1.0 / 0.0024, suck 1.0 / 0.0025, tri 1.0 / 0.0021, longshadow 1.0 / 0.0020, electrify
  0.99985 / 0.022, autolevel 1.0 / 0.0020, displace 1.0 / 0.0023, zap 1.0 / 0.0020.
- Behaviour: longshadow with black colour only darkens (max(out - in) 0.0, min -0.49); electrify and zap only add
  (min(out - in) 0.0; 6.0 % / 2.2 % of pixels lit). Rate 0: two reads 0.5 s apart identical; Rate 10: differ (0.89 /
  0.95 max). Note: the colour pars are shared, so a black longshadow colour also makes electrify / zap add nothing.
- Presets 1-5 recall every stored par exactly (30 pars each, Type included). Cost (median per frame, own TOPs, In TOP
  excluded, clip playing, 120 frames): bend 0.27, suck (black hole) 0.23, tri (triangulate) 0.55, longshadow (preset)
  1.01, electrify (electric) 0.38, autolevel 0.34, displace 0.36, zap (6 branches preset) 2.02 ms (p90 2.99). b3 real
  rate 59.9 frames/s with zap on (onFrameStart counter).
- Not run live: autolevel on a deliberately dimmed input, displace on a Constant TOP / with a Map TOP (offline tests
  cover both).
- **Main** (JazibTD_home.466): slot `misc1` (order 15, enabled 0); bend parity within 1.0; td_errors none; pars back to
  defaults; FX_glitch parked. Capture (b3, black hole): `output/project1_lab_FX_glitch_misc1_out1_2026-10-26T18-49-10-622Z.png`.

## Type `arcs` (TC-03 arc bolts between tracked points; lane D, 27 Oct 2026)
Type menu entry 9. Points page: `Pointchop` (any CHOP: samples = points with channels tx/ty, u/v, x/y or the first
two; or ONE sample with channels x y x y ... as hand / face landmark CHOPs give them; empty = Point + Point 2),
`Pointspace` uv 0..1 / ndc -1..1 / pixels, `Arcmode` chain (in order) / pairs (all within Reach) / nearest
neighbour, `Reach` (frame heights; power = (1 - d / Reach) ^ Arcfalloff, Reach 0 = power 1), `Maxarcs` (<= 32,
strongest first). Ops: `pts_none` / `pts_sel` (Select CHOP: the Points CHOP only while Type = arcs) -> `arcs`
(Script CHOP, maths in the `arcs_logic` DAT = `ARCS_PY`: 2 samples per arc, channels a b c d = x0 y0 x1 y1 px |
power seed) -> fx as `uniform samplerBuffer uArcs` (array0, vec4, texture buffer); arc count in uH.y. Each arc is the
zap bolt (fbm offset, Jag, Width x 1, Rate re-roll) x power, culled per pixel beyond W x 14 + 0.5 x Jag x L (the
glow there < exp(-14)); colour Colour x Glow x Strength, added. Feed: FX_track blob centres, a MediaPipe hand CHOP,
effector positions (any CHOP). Mirror: `fx_glitch_misc_logic._arcs` (+ `ARCS_PY` exec'd offline). Presets 6 arc
pair (Point -> Point 2), 7 plasma web (pairs, Reach 0.45), 8 neighbour sparks (nearest, warm).

LIVE CHECKS (arcs): (1) compiles; td_errors none; the `arcs` CHOP has 2 x arcs samples; (2) pass_seq -> **0**;
(3) points CHOP (Constant / Table -> 5 points uv), pairs Reach 0.5: `arcs` rows = `arc_list` offline (1e-6) and
out1 vs `reference(in1, pars, arcs=...)` within (3/255) >= 0.99 (Rate 0); (4) moving a point re-cooks the CHOP once
(not every frame while still); (5) presets 1-8 full state; (6) cost <= ~3 ms with 24 arcs (per-pixel cull), fps.

### Verified live (arcs: lane D, scratch, 27 Oct 2026, 31550; rack from the builder)
- Compiles, td_errors none. 5 points (Table -> DAT to CHOP, tx / ty uv), pairs, Reach 0.5: `arcs` = 8 arcs, every value
  = `arc_list` offline (max diff 7.4e-8); out1 vs `reference(in1, pars, arcs)` within (3/255) **1.0**, max 0.0020,
  4.7 % of pixels lit. Static points: the CHOP does not re-cook (totalCooks 107 -> 107 over 1 s); one table edit ->
  exactly one cook. pass_seq -> **0 / 0 / 0 / 0**; presets 1-8 full state (Pointchop is an op par, not stored).
- Cost (10 points): arc pair / chain 9 arcs 1.41 / 2.37 ms (median / p90), plasma web 24 arcs 1.98 / 2.97, neighbour
  sparks 7 arcs 0.88 / 1.65; electric 0.89. Project 59.83 fps with plasma web on.

### Fed from FX_track (lane F wiring, 27 Oct 2026; live scratch + main .738)
`Pointchop` = `/project1/lab/FX_track/out_uv` (u v of the valid tracker points; `fx_track.link_fx()` sets it and the
full-state look "tracked arcs", docs/builds/fx_track.md "Outputs"). Changes here: (1) a SET Points CHOP with < 2
points draws no arcs (before: it fell back to Point / Point 2, so one tracked person drew the default arc); empty
Pointchop still = Point + Point 2; (2) `read_points` returns [] for 0 samples (was an IndexError); (3) `arc_list`
takes a numpy path for pairs / nearest at >= 12 points (`arc_list_np`, equal to the loop `arc_list_py`: offline test
`test_numpy_path_equals_loop`, 1e-9): 64 tracked points pairs 3.6 -> 0.74 ms CPU in TD. Measured: misc fx GPU 1.2 ms
with 24 arcs from 64 moving points; when the Points CHOP chain (a TOP to CHOP) cooks inside fx's pull, fx's
`gpuCookTime` reads ~14 ms (the download wait is billed to it, T-200), so pull / time the points first.

## Tri lattice fix (lane D tail, 27 Oct 2026)
`tri` cut its rows with an integer row shift (`xs = x / s - 0.5 j`), so a pixel's triangle often did not contain the
pixel (found while building mosaic cells, which use the true basis (1, 0) / (0.5, sqrt3/2)). New Tri page menu
`Lattice`: equilateral (default for new use: `xs = x / s - 0.5 y / h`) or classic (the 26 Oct look, kept so nothing
changes silently: preset 3 `triangulate` stores Lattice classic). Mirror `_tri` follows `Lattice`.
LIVE CHECK: tri parity (Rate 0) for both lattices within (3/255) >= 0.99; preset 3 recall reads Lattice = classic.
Verified live (tri lattice, scratch then main .712, 31550): tri parity Size 48 equilateral within 0.99993, classic
0.99998 (3/255); `upgrade` on main replaced presets 1-8; preset 3 recall reads Lattice = classic.
