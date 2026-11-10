# MX_prox_material: proximity-driven PBR material for any mesh (26 Oct 2026, TD 2025.31550)

`/project1/lab/MX_prox_material`. User ask (26 Oct): "yes add proximity pbr materials for meshes too" + "proximity can
be just points too - like in ruben fros videos" (`px_requirements.md` item 8). Effector objects (box / sphere / plane
Geometry COMPs, Nulls) and **point sets** (CHOP / TOP / SOP / POP points: face landmarks, depth points, particles, mesh
vertices) drive **lit PBR material properties** and **vertex displacement** of any mesh.

**Status: LIVE-VERIFIED v1 on 31550 (26 Oct), parked.** Offline: 33 tests (`python3 -I -m unittest discover -s test -p
'test_prox_mat.py'`, ~1 s): par / row / header agreement, shader rows, menus vs shader indices, packing, point paths,
CHOP point parsing (samples + FT_face_track channel layout), point images, field vs brute force (numpy), drive maths,
known-distance displacement numbers, combine / flip / gain, effector shapes, presets, glslc compiles of all 4 stages
against TD stubs, builder API + T-70/T-74 text rules.

## Reuse (no bloat)
PX's maths is shared, not copied: `builders/glsl/px_common.glsl` (effector rows, SDFs box / sphere / plane / point,
falloff shapes smooth / linear / gaussian / step / shell / core, combine max / sum / product / screen, ragged noise edge,
value noise / fbm, hue) and `builders/px_logic.py` (effector row packing, affine maths, numpy references). Two small
additions to px_common, used by MX today and available to PX: the point-set functions (`pxPtsNearest`,
`pxPtsDensity`, `pxPtsTexel`, `pxFieldSample` / `pxFieldFetch`, `pxPtsEqDist`) and a `PX_NO_TEX_INPUTS` guard around
`pxMaskTex` (GLSL MATs have no `sTD2DInputs`). PX's 51 tests still pass.

**Shared effector list (26 Oct, offline, LIVE CHECKS X1/X2 in `docs/builds/effectors.md`):** Effectors page `Effsource`
= `list` (new default: the `/project1/effectors` packed buffer `uEffRows`, any count, `Effselect` by name / `#tag`,
`Listfalloff` per effector or this material's Radius / exponent / shape) or `objects` (the v1 `uE[48]` path below,
max 8; `apply_prox_material(geo, effectors=[...])` with objects sets it). Ops `eff_none` + `eff_in` in every unit.

## Files
| File | What |
|---|---|
| `builders/prox_mat.py` | `build(parent)` demo COMP, `build_unit(comp)`, `apply_prox_material(geo, effectors, like)`, `revert_prox_material(geo)`, `park()`, `shader_texts()` |
| `builders/prox_mat_logic.py` | par pages, uMX row table + generated GLSL header, packing, point parsing, presets, demo tables, numpy references |
| `builders/glsl/prox_mat_common.glsl` | `mxProx` (effectors + point set -> w, distance, direction, velocity), `mxDrive`, `mxDisplace` |
| `builders/glsl/prox_mat_vert.glsl`, `prox_mat_pixel.glsl` | GLSL MAT stages (TDDeform: instancing-safe; TD PBR lighting) |
| `builders/glsl/prox_mat_pts.glsl`, `prox_mat_field.glsl` | compute: point set (world xyz + velocity), 3D distance / density field atlas |
| `test/test_prox_mat.py` | offline tests |

## How it works
* **One weight w per pixel / vertex**: object effectors via PX's `pxW` (Radius, Falloffexp, Shape, Combine, Ragged),
  point set as one more source (nearest point minus Pointradius, or soft density -> equivalent distance), combined
  with the same Combine rule, x Gain, Flip. Pixel w is evaluated at the **rest** world position (before displacement),
  so material and displacement agree.
* **Drives** (each near / far / curve: value = mix(far, near, w^curve)): roughness, metallic, detail normal noise,
  emission (colour x strength), rim glow (fresnel x strength), opacity (Opacityon -> blending), displacement.
  Colour modes off / tint / replace / ramp far->near / hue shift / add (amount, curve). Dissolve off / near / far:
  w^curve + offset vs fbm noise (scale, octaves, speed) -> discard, burnt rim band (width, colour, emission, char).
* **Displacement** (vertex, world space, after TDDeform): push / pull, attract (to the effector surface, never past),
  swell ring (peak at w = 0.5), ripple (sin of the surface distance, freq / speed), noise, wake (nearest point
  velocity x Wakegain); direction normal / away from effector / effector axis / world y; Normalfix rebuilds the normal
  from two displaced tangent neighbours.
* **Vertex cache** (`Dispcache`, Displace page, on by default; perf-b2-w4, 28 Oct): `vc_cache` (compute, W 256 x 3H
  rgba32f) runs the vertex displacement (`mxVertDisp`, prox_mat_common.glsl) once per POINT of each cached mesh and
  stores offset / displaced normal / rest point; the vertex shader takes its texel by `gl_VertexIndex` when the stored
  rest point equals its own `TDDeform(TDPos())` (within 1e-5 relative) and otherwise runs `mxVertDisp` itself
  (instancing, skinning, a moved parent COMP, a mesh whose vertex list is not its point list: all fall back, same
  numbers). Slots: `vc_slots` table (slot, geo, `vc_sop<k>` SOP to CHOP P + N of the geo's render SOP) -> `vc_src`
  (Script TOP, SOP-space points, cooks when a SOP changes) + `vc_rows` (Script CHOP -> `uVG` texture buffer: on, W, H,
  n, per slot world rows, normal rows, offset, count; cooks when a geo moves); `vc_s0` / `vc_s1` hand the MAT's sPts /
  sField textures to the pass. A slot needs its own MAT (`uVC.x` = slot): the demo has `mx_mat` (geo_plane),
  `mx_mat_torus`, `mx_mat_sphere`, all on the same `mx_vert` / `mx_pixel` DATs; `apply_prox_material` makes slot 0 for
  its geo. `vcache(comp, [(mat, geo), ...])` re-sets the slots.
* **Time only where used**: `uMXT.x` is `absTime.seconds` only while ripple / noise displacement, a dissolve noise speed
  or a detail-normal speed is set, else 0 (same pixels), so the MATs and `vc_cache` recook only when something they read
  changes (the cache stays put while effectors and meshes stand still).
* **Solid pixel shader**: while `Dissolvemode` is off the MATs use `mx_pixel_solid` (same file, `MX_NO_DISSOLVE`: no
  dissolve `discard` in the program, so early depth / hidden-surface removal work, ~1 ms GPU at 1080x1920);
  `mx_pixel` (with dissolve) is picked by the MAT's `pdat` expression when it is on. The first switch to dissolve in a
  session compiles that program for each MAT (b2: 1.6 s once for 3 MATs, then 0.003 s); switch it once in rehearsal.
* **Uniforms**: one `uMX[80]` vec4 array (48 effector rows = PX's uE layout, `#define uE uMX`, then 32 material rows
  `MX_*` generated from `prox_mat_logic.ROWS`) from the `mx_rows` Script CHOP, + `uMXT` (seconds, frame dt) by par
  expression. `mx_rows` reads pars + effector transform pars, so it cooks when they change (Track = frame forces every
  frame); animated effectors (expressions) recook it each frame (~0.1 ms, measured below).
* **Point sets**: `pts_tex` (Script TOP) turns a CHOP (samples = points `tx ty tz` / aliases, or channel groups
  `<name>x/y/z` like FT_face_track `out_pts`), SOP (`pts_sop`) or POP (`pts_pop`) into rgba32f rows; a TOP source is
  used directly (rgb = xyz, Topstride / Topoffset texels per point, e.g. BO_particles state = stride 3). `pts`
  (compute) applies Pointscale / Pointoffset / Pointspace COMP, stride-decimates to Pointmax (cap 4096 = PX_PTS_MAX),
  and writes velocity rows (frame difference, Velsmooth). Path auto: <= Directmax (64) points brute force per pixel,
  else `field` (compute): Gridres^3 cells over Gridcentre / Gridsize, nearest distance + density + nearest velocity,
  trilinear in the shader (outside the box: + distance to the box).

## Apply to any mesh
```
ns = dict(globals()); exec(open('<repo>/builders/prox_mat.py').read(), ns)
ns['apply_prox_material']('/project1/lab/SOME/geo', effectors=['/project1/lab/MX_prox_material/eff_sphere'],
                          like='/project1/lab/MX_prox_material')      # values copied from the demo (optional)
ns['revert_prox_material']('/project1/lab/SOME/geo')                  # old material back, unit removed (safe_destroy)
```
It builds a material unit `<geo>_proxmat` (baseCOMP next to the geo, ~20 ops, its own pars) and sets the geo's
`material` to its `mx_mat` (absolute path); the previous material path is kept in the geo's storage. Effectors are
names / patterns relative to the unit or its parent, or absolute paths. `unit_parent='<COMP>'` puts the unit in another
(cooking) COMP, e.g. when the geo's own COMP is parked. Any Geometry COMP works, instanced or not
(TDDeform / TDDeformNorm / TDInstanceColor).

## Presets (Presets page: Preset + Apply preset)
molten touch (dark rock -> glowing orange, swell, detail normal), chrome reveal (rough dielectric -> mirror metal),
glow aura (gaussian halo emission + rim, hue shift), dissolve shell (noise dissolve with burnt rim), ripple pool
(ripples on the plane), point stir (point set wake + glow; set Pointop to a point CHOP, demo: `demo_pts`).

## Environment page + Chrome mirror (W1-E, 27 Oct, offline; `docs/builds/px_geo.md`)
Demo-only page: `Envmode` gradient (default = the v1 `env_map`, unchanged) / top (`Envtop`: an HDRI or cube TOP) /
scene (`env_cube`: a low-res cube render of `Envgeo` seen from `Envcentre`, every `Enveveryn` frames, built by
`env_capture()`, which BL_splat_render's Geoenv reuses so chrome objects show the splats). Preset **Chrome mirror**:
metal 1, roughness 0.04-0.06 everywhere. LIVE CHECKS G7 / G9 in px_geo.md.

## LIVE CHECK list
| # | Check | Expected |
|---|---|---|
| M1 | scratch TD first: build + compile (mx_mat both stages, pts, field) | no errors; then main TD |
| M2 | mx_rows cooks only on change | static effectors: totalCooks flat; moving one: +1 per change |
| M3 | far = plain PBR | demo meshes with mx_mat (no effector near) vs ref_pbr on the same geos: small pixel diff |
| M4 | local only | moving an effector changes roughness / emission / colour pixels near it only (read >= 2 frames later, T-74) |
| M5 | displacement maths | plane vertex at distance 0.75 / 1.0 / 1.25 from a unit sphere effector (r 0.5), Radius 1 smooth, push 0.2: offsets 0.16875 / 0.1 / 0.03125 |
| M6 | points | demo_pts direct + field paths light up near the points; field vs direct pixel agreement |
| M7 | apply / revert | on another lab geo, then reverted (material path restored) |
| M8 | perf | out1 1080x1920: COMP cook ms (GPU + CPU), real fps, other COMPs parked |
| M9 | captures | 2-3 presets |

## Live results (26 Oct 2026, TD 2025.31550; scratch TD first, then main; T-115)
| # | Result |
|---|---|
| M1 | Scratch then main: mx_mat (both stages), pts, field compile clean; td_errors clean on main (49 ops) |
| M2 | Static effectors: `mx_rows` / `mx_eff` 0 cooks over 58 pulled frames; one effector move = exactly 1 `mx_eff` cook (0.3-0.5 ms CPU). Material pars: `mx_rows` cooks only on a par change |
| M3 | Effectors far away vs `ref_pbr` (plain PBR MAT, same values) on the same geos, 1080x1920 16F: mean abs diff 5.9e-10, max 4.9e-4 (half-float rounding), 0 px > 1/255 (meshes cover 21 % of the frame) |
| M4 | Sphere effector (r 0.3, Radius 0.6) at x +0.6: 3.9 % of pixels change, all within 289 px of its projected centre (projected influence radius 294 px); moved to x -0.6 the change set mirrors (cols 471..785 -> 294..608) |
| M5 | GPU compute probe of `mxDisplace` (same functions as the vertex stage), unit sphere r 0.5, Radius 1 smooth, push 0.2: offsets 0.16875 / 0.1 / 0.03125 at x 0.75 / 1.0 / 1.25 = numpy reference exactly; w 1 inside |
| M6 | 64 points (demo_pts), 32x32 probe grid: direct path vs numpy max 1.7e-7; field path (48^3) vs direct: w max 0.058 / mean 0.004, distance max 0.029 (0.35 cell). Velocity: points moving +1 unit/s -> 0.996 (Velsmooth 0) |
| M7 | Instanced geo (6 instances) renders with the material (scratch). Main: `apply_prox_material` on the instanced `PV_previz_stage/crowd` (800 instances; unit in MX via `unit_parent` because PV is parked) built clean, then `revert_prox_material` restored `crowd_mat` and removed the unit. Not visible on main: PV is parked and parked geometry does not render (T-115 (4)); un-parking PV is the user's call |
| M8 | 1080x1920, aa2, pane off the COMP, out1 pulled each frame, other lanes running: **default look 2.55 ms** (render 1.87 CPU+GPU, mx_eff 0.43 while the demo effectors animate, 0 when still); **molten touch 4.1 ms** (swell + normal fix ~0.6 ms GPU vertex, detail noise ~0.9 ms); project 59.9 fps (314 render cooks / 5.24 s). Levers: Antialias aa1 (-0.4), detail normal off (Nrmnear 0), Normalfix off, fewer Nrmoct |
| M9 | Captures (scratch, same build): `output/prox_mat/cap_molten_touch(_preview).png`, `cap_chrome_reveal.png`, `cap_glow_aura.png`, `scratch_dissolve.png` |

### Perf wave 4 (b2 -> main, 28 Oct 2026, TD 2025.31550; PERF_FINAL_27OCT.md "b2, wave 4", LEARNINGS T-230)
Vertex cache + solid pixel shader + time-gated uniforms. Parity on b2 (static scene, 1080x1920 16F out1): new vs the
old build 2 px differ (max 2.4e-4 = half-float rounding, from the shared `mxVertDisp` loop); Dispcache on vs off
bit-exact for swell / ripple (speed 0) / push outward / wake, attract 6 px <= 1e-3. Cost on b2 (load ~5, b3 lane on
the GPU): old 5.8-7.0 ms (CPU ~1.0) in alternating windows vs new 4.6 ms still (CPU 1.0, GPU 3.6), 5.7-6.3 with a
moving list effector (vc_cache recooks: +0.45 CPU, +0.7 GPU). Still over 3 ms: the Render TOP CPU floor (~1 ms,
T-198) and the per-pixel proximity (~2 ms GPU, evaluated at the rest position of every pixel; no exact shortcut).

TD's own PBR export (`pbrMAT.outputShader('name')`) saved for reference to `output/pbr_export_31550_{v,p}.glsl`; the
lighting block follows it (T-115 (1)). Known: `td_layout check` reports `pts_fb -> pts` as a back wire (Feedback TOP
`top` reference, T-85 (6), handler fix pending); chrome looks best with a brighter environment than the default gradient
(point `env1` at an HDRI TOP).
