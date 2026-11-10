# PX_pointfx looks on Gaussian splats (b4 verify lane, 27 Oct 2026, TD 2025.31550)

Read-only check of every `px_presets` look on real splats (px_requirements items 6 / 9). No builder edited, nothing
brought home; main touched only for one read-only save (`output/transfer/PX_verify_b4.tox`, 01:16, i.e. BEFORE the
splat lane's commit 95a197a "looks on splats", so main's PX had no `(splats)` presets yet). The sorter was never
touched (T-124).

**Method.** Tox loaded into b4 `/project1/lab`, un-parked. b4's timeline was paused after its restart (`/local/time`
play False: nothing cooked, frame stuck at 615), so it was started. Each run: base (Amode file, source, Bmode off, Morph
0, Actormode off, Pool 0) -> `Presetname` + `Recall` -> Render set (a gen source switched to the splat file) -> ~5 s ->
errors / warnings / `eng_info` -> 150-frame cook sampler (`px_checks.perf_start/report`, comp median = sum of op
cook ms) -> `out1.save`. Load: other TDs busy (real fps 11-43), so costs are relative, not budgets.
Three passes: **A** truck.splat (`media/demo/splats`, Quality std 131 072 = 5 % of 2.54 M splats) for the D looks and
hand_push_cloud; the v1 looks on their own splat files (nike.splat, hornedlizard.spz). **B** SmileyPinata.spz
(Quality custom 228 287, Camdist 4.4: framed small). **C** the splat lane's `splat_variant` recipe by hand on truck
(SPLAT_SCENES truck values, Quality high, Bright x 0.5, Clip 2.2 for Slice bike / Tile city).

**All runs:** 0 errors, 0 warnings; `eng_info splat` = 1 under splats (`drawn` 0 = sprites off, or the pool count),
splat 0 under sprites; sorts kept running. Every look rendered real anisotropic splats (ellipses/shards, not dots).

| Preset | Works on splats | What's wrong (pass A unless noted) | Cost comp ms, splats / sprites | Captures (`output/`) | Suggested splat-version change |
|---|---|---|---|---|---|
| dissolving_scan (nike) | y | reads as a fiery dissolve with smooth splat smears; the nike shape is less legible than as sprites | 12.7 / 8.7 | px_splat_look_dissolving_scan(_sprites).png | Bright x 0.5; Aperture 3 -> ~1 (DOF footprint blurs splats into smears) |
| hand_push_cloud (gen ball -> truck) | partly | the look is built on a generated ball; on truck splats it is a washed-out white field (camera Camdist 3.6 inside the 6 m-clipped scan, Bright 2) | 12.9 / 7.6 (B: 9.7 / 8.2) | px_splat_look_hand_push_cloud(_sprites/_pinata_*).png | needs a scene: truck values + Bright x 0.5, or keep it gen-only (no splat version) |
| ember_splat (lizard) | y | burn + embers read; splat lizard bright cream, embers present; costliest look | 25.3 / 8.1 | px_splat_look_ember_splat(_sprites).png | Aperture 7 -> 2 (big DOF discs cost srender) |
| scan_morph (nike -> lizard) | partly | mid-morph (0.5) splats keep their own file scales, so lizard-sized splats on nike positions read as large overlapping ovals / soft blobs, not a crisp morph | 20.6 / 12.0 | px_splat_look_scan_morph(_sprites).png | Splatscalemult ~0.5 while morphing (or scale by morph progress); Aperture 5 -> 1 |
| lattice_collapse (nike) | y | lattice reads (striped cell blobs), but red is blown pink/white | 12.3 / 6.5 | px_splat_look_lattice_collapse(_sprites).png | Bright x 0.5 |
| KANDA swipe | **n (A)**, y (C) | A: full-frame pale fog (camera at an inherited Camdist 2.8 inside the truck scan, 5 % decimation leaves big near splats, Bright 2). C: photographic truck + swipe, still white fog in the lower half (near ground splats) | A 18.6 / 5.2; B 9.4 / 13.5; C 14.8 | _kanda_swipe(_sprites/_pinata_*/_splatvariant).png | splat lane's recipe works; add Clip ~3 (or a near-camera fade) to kill the ground fog |
| Hanging streaks | **n (A)**, y (B) | A: solid beige wash. B (pinata): streaks read as vertical stretched splats | A 20.0 / 6.4; B 13.5 / 13.2 | _hanging_streaks(_sprites/_pinata_*).png | splat recipe (Camdist 4.4, Bright x 0.5) |
| Alley people fire | **n (A)**, y (B) | A: wash. B: actor (cyan/orange) + burning scene + embers as sprites over splats: reads (S5 OK) | A 13.6 / 8.6; B 12.2 / 15.3 | _alley_people_fire(_sprites/_pinata_*).png | splat recipe |
| Radial blast | partly (A), y (C) | A: blown white streaks + one screen-sized near splat. C (Bright 1.3): wire-like truck, bottom blurred by near ground splats | A 9.2 / 6.7; B 11.4 / 11.2; C 11.5 | _radial_blast(_sprites/_pinata_*/_splatvariant).png | recipe + Clip ~3 |
| Slice bike | **n (A)**, y (C) | A: pale fog. C (Clip 2.2): clean small truck; bands barely visible at this frame / distance | A 14.6 / 10.3; B 12.1 / 11.4; C 17.0 | _slice_bike(_sprites/_pinata_*/_splatvariant).png | recipe; Camdist ~3 or slice gap up so the bands read at 4.4 |
| Tile city | **n (A)**, y (C) | A: white fog even at Aperture 0. C: the scan breaks into flying splat shards (reads as tiles breaking, more violent than the sprite slabs) | A 13.5 / 6.2; B 13.3 / 12.2; C 16.1 | _tile_city(_sprites/_pinata_*/_splatvariant).png | recipe (Clip 2.2 holds) |

**Findings for the owner lane (b5):**
1. The splat lane's `splat_variant` recipe (truck scene values, Bright x 0.5, Clip 2.2) is what fixes the D looks:
   pass C turns pass A's full-frame fog into a readable photographic truck. Built-ins on truck without it fail on splats.
2. The remaining fog comes from **near-camera splats**: real splats have no `Maxpx` cap (sprites do), so a few splats
   within ~1 m of the camera fill the frame. The fix with the most effect, if the owner wants a code fix: clamp the splat 2D
   footprint by `Maxpx` or fade splats inside a near distance in `px_splat_adapter.glsl`. Otherwise lower Clip per look.
3. `Size` has no effect on file splats (adapter uses rest scale x per-point size only; Size 0.002 vs 0.009 identical),
   and splat scales are not multiplied by `Ascale`. `Splatscalemult` is the only global knob (0.2 cleared most fog:
   `px_splat_diag_kanda_*.png`). Worth a doc line.
4. truck.splat at std / high keeps 5-10 % of 2.54 M splats: holes + oversized survivors. For splat looks, prefer Quality
   high / custom up to the 524 288 cap, or a natively small scene (SmileyPinata 228 k, no decimation).
5. Partial presets inherit (T-124 (1)): v1 looks set Camdist / Aperture / Size, D looks don't, so a D look after a
   v1 look runs at the wrong camera (Camdist 2.8 here). Effectors accumulate across recalls (6 after this run; MAX_EFF 8).
6. The v1 looks (dissolving_scan, ember_splat, scan_morph, lattice_collapse) work on splats as stored but want Bright
   x 0.5 and lower Aperture (DOF footprints on splats cost 5-10 ms more srender: ember_splat 25 ms vs 8 ms as sprites).
7. Cost: splats = sprites + ~4-12 ms (srender 3-10 ms GPU, Sort POP ~2 ms per sort, every 2nd frame) under load.
