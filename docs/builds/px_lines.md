# PX_lines: the lines pass for point / splat scenes (lane W1-C, 27 Oct 2026, TD 2025.31550 target)

User (27 Oct): "including the green lines ... and all", colours changeable. Ruben Fro's thin bright neon lines
(`RUBENFRO_COVERAGE.md` 1a, G1-G7; evidence `docs/research/BR_rubenfro_pointcloud_fx.md` 4d.1, frames in
`research_src/rubenfro/yt2/`). **Status: phase 1 OFFLINE done** (builder + numpy references + 35 offline tests +
glslc). **Phase 2 LIVE done on the scratch TD (27 Oct, 2025.31550): LC1-LC14 pass; results in "Verified live" at the
end; then built in main by the builder (see "In main").**

One COMP, `PX_lines`, usable two ways:
* **standalone over any TOP**: `in1` = scene, `in_points` = any rgba32f TOP whose texels are xyz, `in_depth` = linear
  eye depth (optional), own `cam` or `Camera` = any Camera COMP; `out1` = lines composited over `in1`.
* **as PX's lines layer** (wave-2 PX owner wires it; this lane did not edit `px.py` / `px_logic.py`): build it inside
  `PX_pointfx` (`build('/project1/lab/PX_pointfx')`), `Outmode` lines, `in_points` = PX `update` (state texture),
  `Ptstride` 5, `Ptcount` = PX count, `Camera` = `pcam`, `in1` = `sw_render` (alpha occlusion / edges), and add `out1`
  into PX's chain **before** `trail` / `glow` so PX's bloom catches the HDR lines.

## The seven line kinds and how each works
| Kind (coverage row) | Source | How |
|---|---|---|
| Concentric neon rings (G1) | `rings` | K rings x S segments per centre; centres = up to 4 objects (`Ringops`: their translate, y axis = ring normal, scale = radius scale) or `Ringcentre` / `Ringnormal`; `Ringface` camera turns them to the camera. `Ringexpand` (cycles/s) moves rings outward with a sin fade in / out (TFM 40-60 s); `Ringtilt` + `Ringorbit` tilt every ring about an in-plane axis that turns per ring and over time (atom-like orbits, TFM 600-620 s); `Ringspin`. Rainbow ring (OSC): `Linecolsrc` attr + `Ringattr` along + a cycle palette. |
| Edge / outline lines (G2) | `edges` (post) | One compute at `Edres` (half): 3x3 Sobel at +-Edwidth/2 px of luma, alpha and (with `Usedepth`) depth relative to depth; smoothstep threshold; reveal / cut along a screen wipe (`Edwipe` deg); world mask through the depth (pixel -> world from the inverse view-proj). Colour: `Edgecolsrc` (source = the scene's own colour at full brightness, so shop fronts keep their hue), attribute luma / depth / wipe / height. `Bgdim` darkens the rest (TFM 320-370 s "the rest dark"). |
| Light-trail ribbons on the ground (G3) | `trails`, motion `flow` or `points` | History compute (`hist`, ring buffer `Trtracks` x `Trsamples`, one sample every `Trevery` frames). `points`: the head IS a point of `in_points` (PX moving points / pool / actor leave trails; a jump > `Trmaxjump` = new life, no bridge). `flow`: own particles spawned on random points, moved by `Trdir` x `Trspeed` + an analytic divergence-free curl field + a vortex; respawn after `Trlife`. Width taper + fade along. Floor ribbons: `Trdir` toward the vanishing point, small curl, points = the floor. |
| Slice / contour lines (G4) | `contour` | Per sampled point: distance to the nearest band (planes every `Ctspacing` along `Ctaxis`, x / y / z / camera forward / custom); inside `Ctband` -> a short segment (`Ctlen`) along the band's tangent (around the axis = rings on bodies, or across the view), snapped onto the plane, so the dots join into lines. `Ctspeed` scrolls bands, `Ctwave` / freq / speed make waves travel along them (DR1 40-52 s). Line id = band index (`Ctattr` index -> one colour per band). |
| Line vortex / lightning tendrils (G5) | `trails` flow + `connect` | Vortex: trails with `Trswirl` / `Trpull` around an axis (`Trvcam`: around the camera, tendrils converge on it, BA2 78 s) and `Trjitter` (per-sample random offset re-rolled at `Trjitterhz`: lightning). Connect: each of `Cnpoints` sampled points to its `Cnk` nearest within `Cnradius` (brute force n^2 in the seg compute), alpha (1 - d/R)^2 (plexus), `Cnsub` pieces with mid-point jitter (zigzag lightning; i -> j and j -> i draw the same zigzag). |
| Wireframe polylines, logos, typography (G6) | `polyline` | A CHOP (`Polychop`: tx ty tz [w], samples = points in order) (a SOP: through your own SOP to CHOP), CHOP to TOP -> one row; placed by `Polyop` (any object); `Poclose`; pen up where w < 0 or a gap > `Pomaxgap` (glyphs of a Text SOP). Draw-on with `Reveal` (u = point index / count). |
| Sweep beam (G7) | none here | Already covered by PX's plane effector + `Glow` (A5) + `prox_colour`: reused, not duplicated. |

Shared look controls (every source): `Width` (core, real px at any depth: the quad is built in screen space), `Halo`
(Gaussian halo radius px) + `Halogain`, `Intensity` (HDR, so bloom catches it), `Blend` add (crossings brighten) / max
(clean joints; LIVE CHECK the blend-op par), `Reveal` / `Cut` / `Revsoft` (draw-on and erase along each line's u),
`Dash` / `Dashduty` / `Dashspeed`, `Flicker` / `Flickerhz` (per line), world `Mask` (sphere inside / front: behind a
plane, from `Maskop` or pars, `Maskinvert`: lines appear per region as a front passes), `Occlusion` over / depth (vs
`in_depth`, `Occbias` / `Occsoft`) / alpha (behind the scene's coverage). Per-source gain + colour attribute.

**Colour (W1-B convention, `docs/builds/palette_convention.md`):** `uPal[16]` from the `pal` Script CHOP
(`palette_map_logic.palette_stops` -> `pal_rows`; `Palsource` stop preset / custom table `pal_stops` / file,
`Palmode`, `Palinterp`, `Palreverse`, `Palshift` = the drive target), `uPalCtl` = (count, shift, mode, interp);
`uLineCs` (`Linecol`, `Linecolsrc`, `Linepalpos`, `Linepalspread`, `Linekeep`) for all segment sources and `uEdgeCs`
(`Edge*`) for edges, `pxColSrc(cs, solid, src, attrT)`. attrT per source (`Ringattr`, `Ctattr`, `Trattr`, `Cnattr`,
`Poattr`): along (u 0..1), index (ring k / band k / track k: with mode `index` = stop k), depth (`Depthnear`..`far`),
random. Colour is resolved once per segment in the seg compute (the MAT has no palette).

## Files
| File | What |
|---|---|
| `builders/px_lines.py` | builder: `build(parent, name)`, `panel()` (zkit, separate exec >= 5 frames later), `park()`; callback texts `ROWS_CB` / `PAL_CB` / `PEXEC` |
| `builders/px_lines_logic.py` | pure logic: par schema `PAGES`, `plan` (segment ranges), `rows` (uL[]), `glsl_header` (#define R_*), camera maths, `cs_vec` / `pal_spec`, perf model, float64 references `ref_segments` / `ref_ring_segments` / `ref_hist_step` / `ref_curl` / `ref_quad` / `ref_coverage` / `ref_edges` / `ref_comp` / `ref_mask` / `ref_reveal` |
| `builders/glsl/px_lines_common.glsl` | uL / uT, hash (pcg), world mask, reveal |
| `builders/glsl/px_lines_seg.glsl` | segment generator (one compute): rings, contour, trails, connect, polyline |
| `builders/glsl/px_lines_hist.glsl` | trail history (one compute + Feedback) |
| `builders/glsl/px_lines_vert.glsl`, `px_lines_pixel.glsl` | GLSL MAT: instanced screen-space quads, core + halo, caps, reveal / dash / occlusion |
| `builders/glsl/px_lines_edges.glsl` | edge lines (one compute) |
| `builders/glsl/px_lines_comp.glsl` | composite / lines-only (one compute) |
| `builders/px_lines_checks.py` | live checks in TD: `harness()` (disposable PL_harness: Fibonacci sphere, moving points, chart, depth, path CHOP), `case(name)`, `check(name)` (vs the references), `pump(n)` + `perf_report()`, `drop_harness()` |
| `test/test_px_lines.py` | 35 offline tests (~2 s): `python3 -I -m unittest discover -s test -p 'test_px_lines.py'` |

Shader text of a stage = `glsl_header()` + (`px_palette.glsl` in seg / edges) + `px_lines_common.glsl` + the stage.

## Network
```
rows (Script CHOP -> uL[NROWS]; cooks on par edits, per frame only while following Ringops / Polyop / Maskop / Camera)
pal (Script CHOP -> uPal[16], re-binds uPalCtl count) + pal_stops (Table) ; pl_logic, pl_palmap (Text DATs) ; pl_pulse (Reset)
in_points -> hist (compute; hist_fb) -> hist_sw            Polychop -> poly_top (CHOP to TOP) -> poly_sw
in_points + hist_sw + poly_sw -> seg (compute, rgba32f 1024 x ceil(Maxseg / 256))
seg -> lmat (GLSL MAT) on lgeo (1x1 quad, instances = rows G0.z) + cam/Camera -> render (16f, Resx x Resy) -> render_sw
in1 + depth_sw -> edges (compute, Edres) -> edges_sw
in1 + render_sw + edges_sw -> comp (compute, 16f) -> out_sel (Amount 0 = in1) -> out1
```
Every GLSL TOP has <= 3 wired inputs (T-84 / T-88); every multi-pass stage is a compute (T-46 / T-47). Parts that are
off sit behind a Switch on `black` (8x8) and do not cook (hist, poly, render, edges, depth).

### Texture layouts
| Texture | Size | Content |
|---|---|---|
| seg | 4 x 256 wide, ceil(Maxseg / 256) high, rgba32f | segment s at (4 (s % 256) + k, s / 256): T0 = A.xyz, uA; T1 = B.xyz, uB; T2 = rgb (HDR, x Intensity), alpha (gain x mask x flicker); T3 = width mult, caps (bit 0 start, bit 1 end), line id, source + 1 (0 = none; 1 rings, 2 contour, 3 trails, 4 connect, 5 polyline) |
| hist | (Trsamples + 2) x Trtracks, rgba32f | col 0 = head P, age; col 1 = life id, life, reset count; col 2 + i = slot i: P, life id + 1 (0 = never written); newest slot = floor(frame / Trevery) % Trsamples |
| poly_top | N x 1 | texel i = x y z (w < 0 = pen up) |
| edges | Edres, rgba16f | rgb = colour x gain x e, a = e |

`in_points`: point id -> texel ((id % side) x Ptstride, id / side), side = width / Ptstride; count = Ptcount (0 = all
texels). PX's state texture has no validity flag: dead pool points sit at the bounds centre (they may grab contour /
connect segments there; point PX's `Ctfirst` / `Ctcount` etc. at the scene layer).

## Perf (model `perf_model`, fill calibrated on the live run; measured numbers: "Verified live")
| Case | Segments | GPU est. |
|---|---|---|
| 64k segments, Width 2, Halo 0 (target) | 65 536 | **0.63 ms** (vertex 0.23, fill 0.27, seg 0.05, comp 0.08) |
| 64k, Halo 4 | 65 536 | 3.09 ms (fill 2.73) |
| default (4 rings x 128) | 512 | 0.12 ms |
| connect 4096 points (n^2 search) | 12 288 | 0.7 ms (search 0.50) |
| edges at half res | - | ~0.15-0.27 ms |
Plus the Render TOP's fixed CPU cost (0.7-1.9 ms here, T-143) unless the PX owner draws `lgeo` inside PX's own Render
TOP (add `lgeo` to its `geometry` list: one render, both MATs). **At 64k segments the halo is the cost (it is fill):
keep Halo 0-2 for dense sources and let PX's bloom (lines are HDR) make the glow; use Halo for few lines (rings,
polylines).** Levers: Maxseg, Ctmax, Trtracks x Trsamples, Cnpoints (n^2), Edres, Halo.

## LIVE CHECKS (phase 2: only on the TD the main session assigns, T-144; disposable harness COMP, deleted after)
Reads: `numpyArray(delayed=True)` in a separate exec >= 2 frames after a change, read twice, keep the second (T-74 /
T-91); never in the builder. Expected numbers come from `px_lines_logic` references (tests pin them).
| # | Check | Setup | Expected |
|---|---|---|---|
| LC1 | build + compile | `build()` in the harness; `td_errors`; then `panel()` >= 5 frames later | clean; `seg`, `hist`, `edges`, `comp`, `lmat` compile on 31550 (glslc only checked syntax); `missing` = [] or only par names to fix (`blendop`, `dataformat`, `bgcolora`, `normals`) |
| LC2 | uniforms | read `rows` CHOP and seg's `uPal` / `uPalCtl` / `uLineCs` pars | rows = `px_lines_logic.rows(pars, ctx)` (56 x 4, 1e-6); `uPalCtl.x` = stop count (neon_green 4); rows cooks once per par edit, 0 times per frame with nothing followed (cook count over 300 frames) |
| LC3 | rings vs reference + px radius | defaults (4 rings, Ringradius 1 for the radius check, own cam) | seg texels 0..511 = `ref_segments` (max err 1e-5); Ringradius 1 at the default cam: projected radius **260.735 px** (+-0.5) on the 1080 x 1920 render (capture: ring centre (540, 960)) |
| LC4 | contour on a unit sphere | `in_points` = 4096 points on a unit sphere (harness: GLSL TOP writing a Fibonacci sphere), Contour on, Rings off, axis y, spacing 0.1, band 0.02, len 0.04 | 21 band ids -10..10; ~20 % of segments valid; segment midpoints y = 0.1 x band (1e-5); = `ref_segments` at 1e-4 |
| LC5 | width constant across depth | two rings at z 3 and z -20, Width 3, Halo 0, Blend max | cross-section through each line: core FWHM 3 px (+-0.5) at both depths |
| LC6 | edges on a chart | `in1` = white 1/2-size square on transparent black, Resx 216 Resy 384, Edges on, Edwidth 2, Edres half | `edges` = `ref_edges` at 1/255; e = 0 inside / outside, > 0.99 on the border, <= 4 px per row; `Reveal` 0.5 shows only the left edge |
| LC7 | trails (points) | `in_points` 16 points moving +0.1 x per frame (harness), Trtracks 16, Trsamples 8, motion points, Play | 7 valid pieces per track, each 0.1 apart in x; a 99-unit jump -> that track's first piece invalid for one history |
| LC8 | trails (flow) + Reset | Trmotion flow, no points, Trlife 0.1 | lives respawn (col 1 x grows); Reset pulse -> Resetn + 1 -> all life ids 1, history cleared next cook |
| LC9 | connect | 4096-point sphere, Cnpoints 256, Cnk 3, Cnradius 0.4, Cnsub 3, Cnjitter 0.05 | = `ref_segments` (1e-4; ties in distance may order differently); mutual pairs identical zigzags |
| LC10 | polyline | Polychop = Constant CHOP 4 samples tx (0 1 1 0) ty (0 0 1 1) tz 0, Poclose | CHOP to TOP maps tx ty tz -> r g b (note the working par names); 4 segments, the 4th back to the start; Reveal 0.5 draws half |
| LC11 | occlusion | `in_depth` = constant 4.0 (R), Usedepth, Occlusion depth, a ring at z 0 (eye depth 5) | ring hidden (eye 5 > 4 + bias); constant 6.0 -> visible; check `gl_FragCoord` vs texture orientation (a half-plane depth image hides the matching half) |
| LC12 | palette | Linecolsrc index, Ringattr index, Palsource neon_trio, Palmode steps | ring k = stop k mod 3 (seg T2 rgb = stop x Intensity, 1e-5); Palshift 1/3 moves every ring one stop on with no recompile |
| LC13 | in PX | PX on truck.splat (points) and SmileyPinata (splats), lines layer before glow | rings + contour + edges visible, bloom picks them up; record PX ms with and without the layer |
| LC14 | cost | 64k contour segments, Halo 0, then Halo 4, others parked, pane off the COMP, out1 pulled | seg / render / comp ms per op; target <= 1 ms GPU at Halo 0; real fps recorded |

## Known risks / open points
* TD par names not yet seen live: GLSL MAT `blendop` (max blend; missing -> additive), CHOP to TOP `dataformat`, Render
  TOP `bgcolora`, Rectangle SOP `normals`, Camera `viewanglemethod` (vertical fov assumed horizontal unless it says
  vertical). The builder records any it cannot set in `missing`.
* Script CHOP dependencies: `rows` re-cooks on par edits by reading them (T-115); objects / an outside camera are
  followed through a `Frame` par bound to absTime.frame only while one is set (T-125 (2) / T-143 pattern).
* Composite and edges sample `in1` with normalized coordinates (any size); the render is Resx x Resy.
* u and eye depth are interpolated linearly in screen space within a segment (short segments: invisible error).
* Dead PX pool points are not filtered (see Texture layouts).
* Connect duplicates (i -> j and j -> i) draw twice: identical with Blend max, double with add.

Sources: our own research (BR 4d.1, RUBENFRO_COVERAGE); standard techniques: screen-space line expansion (e.g. the
GPU line rendering used across TD / three.js line materials), Sobel edges, curl of a vector potential (Bridson et al.
2007), plexus k-nearest links. No code copied.

## Verified live (27 Oct 2026, TD 2025.31550, scratch TD; 3 other build TDs + PX splats running = loaded GPU)
Method: `builders/px_lines_checks.py` on the scratch TD: `harness()` (test TOPs wired into PX_lines), `case()` /
`check()` per row (delayed reads, the first read of a change is stale: read twice, T-91), `pump()` pulls out1 once per
frame for 180 frames, `perf_report()` = per-op median cpu / gpu ms. First GPU frames at 270x480 and 4k segments, raised
to 1080x1920 / 64k after clean frames. Live fixes made: LEARNINGS T-168.

| # | Result |
|---|---|
| LC1 | 0 errors / warnings after the fixes; all 4 computes + the MAT compile on 31550; zkit panel 158 knobs (666 x 2601); `missing` = [] |
| LC2 | rows CHOP = `rows(pars, ctx)` max err 5.3e-7; rows cooked once per par edit (15 -> 16 over 156 frames with one edit) |
| LC3 | rings seg vs `ref_segments` max err 3.5e-7; Ringradius 1 at 270 px wide: radius 65.15 px vs 65.18 expected (-0.03 px) |
| LC4 | contour on the 4096-point Fibonacci sphere: 21 band ids -10..10, valid 19.9 %, 0 validity mismatches, max err 5.7e-8 |
| LC5 | Width 3: FWHM 3 px at eye depth 5 and at 25 (coverage sums 4.5 = 3 px x 1.5 both) |
| LC6 | edges vs `ref_edges` max err 3.9e-4 (16f); inside / outside 0, border 1.0, 4 px per row; Reveal 0.5: only the left edge (2 px) |
| LC7 | trails (points): 7 pieces per track, each -0.1 x apart (one frame); a jump: the pieces across it invalid in the next read, a new life id |
| LC8 | flow: life ids grow (respawn every ~0.1 s), no NaN, P within the sphere; Reset: Resetn 0 -> 1, life ids restart at 1 |
| LC9 | connect 256 x 3 x 3 on the sphere: 2304 / 2304 valid, 0 slot mismatches, max err 9.1e-8 |
| LC10 | CHOP to TOP needs `dataformat rgb` for 3 channels (T-168 (3)); 4 segments, closed, max err 2.4e-8; Reveal 0.5 draws 2 sides (`lc10_reveal`) |
| LC11 | depth 4.0 hides a ring at eye 5, 6.0 shows it; alpha mode with a bottom-left alpha quadrant hides exactly that quadrant (gl_FragCoord and texture agree) |
| LC12 | index palette: ring k = neon_trio stop k mod 3 (x Intensity), max err 3.2e-7; Palshift 1/3 = one stop on, no recompile |
| LC13 | over PX_pointfx (library tox, SmileyPinata splats, rest stack): in_points = PX `update` (Ptstride 5, 228 287), Camera = pcam: contour bands + orbit rings + edges line up with the splats (captures in the lane scratchpad; look: bands coloured per index over the dimmed scene) |
| LC14 | 1080x1920, 64k contour segments (all valid), Halo 0: render **GPU 1.07 ms** + CPU 1.17, seg 0.03 + 0.18, comp 0.31 + 0.20; PX_lines total 4.0 ms (real fps 28.5, loaded machine); Halo 4: render GPU 3.63 ms; mixed (contour 32k + trails 512 x 32 flow + connect 1024 + edges, Halo 2): render 0.99 + 1.29 CPU, seg 0.55 (connect n^2), edges 0.27, hist 0.04 GPU; total 4.9 ms |

Not met: the 1 ms GPU target at 64k is 1.1 ms for the render alone under this load (GPU shared by 5 TDs; quiet ~1/2,
px.md); the Render TOP CPU floor (~1.2 ms) is on top unless PX draws `lgeo` in its own render. Halo is fill: at 64k use
Halo 0-2 and PX's bloom. Rows used to cook every frame (1.7 ms) while a Camera was set: now only when a compute reads
the camera (`FOLLOW`).

## In main (27 Oct 2026, JazibTD_home.550 / .552)
Built by the builder in the main TD (`build()`, then `panel()` in its own exec: 157 knobs), no errors; stage box warning
"Invalid path for node .../annotate/annotation" on a fresh stage box cleared with `initializeExtensions()` (T-170).
Placed in the lab plan's **Sims + point clouds** stage after PX_pointfx (`jz_stages` + `restage`: ok, no intruders /
overlaps). Rings check in main: seg vs reference max err 3.5e-7. Cost in main (default 4 rings, 1080x1920, network pane
ON the COMP, so viewer tiles also cooked edges / hist): PX_lines 4.4 ms (render 1.40 CPU + 0.27 GPU, comp 0.19 + 0.68,
seg 0.27 + 0.08; edges 0.48 + hist 0.34 only from the viewers), real fps 51.7 with the other lanes; library export
cook 2.2 ms CPU / 1.35 GPU. Rests **parked**, default state (4 green rings, no inputs). Library: `library/PX_lines/`
(0.1.0). Wiring into PX = wave 2 (PX owner).

## In PX (wave 2, 27 Oct 2026; docs/builds/px.md "Wave 2")
`PX_pointfx/PX_lines` is built by `px.py` (`_lines`): Outmode composite (scene + lines in one compute, no extra op),
in1 = the scene (geo_out), in_points = `update` (Ptstride 5, Ptcount = count), in_depth = `lines_depth` (geometry
depth, Usedepth = Linesdepth and Geoon), Camera = pcam, palette pars linked to PX's Palette page; `sw_lines`
(Lineson) feeds trail / bloom / haze. Live b5: off = diff 0, rings vs ref 3.2e-7, ~2.8 ms with rings + 32 k contour.

## Connect on the whole cloud (wave 4, PX owner, 27 Oct 2026; docs/builds/px.md "Wave 4")
Connect page `Cnindex grid`: `cn_src` (Cnindextop, else in_points) -> `cn_index` (compute: N^3 voxels of the box
Cngridcentre +- Cngridsize / 2, N = Cngrid rounded to 8; one workgroup per 8^3 brick walks every point and keeps one
representative per voxel with shared atomicMin of (priority << 22 | id), priority = random (Cnpick random) or the
distance to the voxel centre) -> `cn_idx_sw` / `cn_rest_sw` (black unless Connect + grid) = seg inputs 3 / 4 through
seg's `tops` par (T-88). Each of Cnpoints samples links to its Cnk nearest representatives within Cnradius in the 27
voxels around its index position; search in the index space (static topology), drawn at the in_points positions. Brute
force stays <= 4096 points (rows clamp + shader guard). Mirrors: `ref_index`, `ref_segments(index=, index_points=)`.
Inside PX: Cnindextop = `source` (rest, cooks once per scene), Cnistride 4, box = the scene bounds (px_rt `_lines_box`);
PX-owned pars are expressions so a look recall does not reset them (T-192). Live b5: index and segments = the references
exactly; 65 536 samples: seg 0.27 + 0.38 ms. Tests: `test/test_px_wave4.py` (SA33*).

Rows (wave 4b): `rows_static` = the par-driven rows (cooks on par edits; while following objects / an outside camera
it reads no world transform, which would make it cook every frame) -> `rows` = a copy + only the object / camera rows
(`px_lines_logic.FOLLOW_ROWS`, `rows_follow`) per frame while following. Live b5: 2.3 -> 0.42 ms CPU per frame.
