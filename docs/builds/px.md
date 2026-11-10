# PX_pointfx: modular point-cloud / splat FX (live in main, splats verified 27 Oct 2026, TD 2025.31550)

`/project1/lab/PX_pointfx`. A point cloud (file scan, Gaussian splat scene, the depth camera, or a generated shape,
or a morph between two of them, plus an optional **actor layer** and an **ember pool**) goes through a **stack of
effector modules** that the user adds, removes, reorders and duplicates. Proximity modules are driven by **visible
effector objects** (boxes, spheres, planes, Nulls, CHOP points, point sets, the actor, the camera) seen as gizmos in a
preview; effectors can follow **motion paths**, leave **trails** and **glow** in the output. The look is rendered as
sprites (soft / shapes / oriented cubes and slabs) or as **real anisotropic Gaussian splats** (BL_splat_render's shader,
reused) and graded to `out1`.
Binding user rules: `docs/builds/px_requirements.md` (items 1-9). Look research + per-module maths:
`docs/research/BR_rubenfro_pointcloud_fx.md` (section 4; v2 = the 4b/4c effector study). Splat / point-cloud loaders:
`BL_gaussian_splats_pointclouds.md`, reused from `BL_splat_render` / `BL_cloud_morph` (their `*_logic.py` files are
copied in read-only; `splat_render.glsl` is read at build time and shared through empty-by-default hooks). Clean-room.

**Status: v2 BUILT LIVE on main (26 Oct 2026, TD 2025.31550; "v2 live results" at the end), merged with v1's live
fixes (glow pass, pcam-free camera maths, Frame-clocked engine CHOPs, lazy panel). Perf pass done on the scratch TD
(26 Oct, "Perf pass" at the end): event-driven engine 2.5-3.3 -> 0.2-0.4 ms/frame, high 262k 11-13 -> 7.3-9.1 ms, splats
27-32 -> 14-20 ms (same-minute, 6 TDs loaded); std / high / splat targets still over under that load (why: see there).** 91 offline tests
pass (`python3 -I -m unittest discover -s test -p 'test_px.py'`, ~12 s): schema <-> GLSL agreement (incl. every menu
index the GLSL hard-codes), codegen (chunk wrapper, pool slots), packing, stack edits, presets (6 built-ins), reference
maths (fronts, wake, point sets, bend, splat covariance stretch + DOF, slices, ember cone, motion paths, trails,
quaternions, glow), perf targets, and **glslc compiles** of every generated shader (each module alone, all + duplicates,
in-place, each built-in look, source, sort keys, layers, post, trail, sprite vertex/pixel, BL's splat shader alone and
with both PX adapters) against stubs of the TD functions used. glslc is a syntax/type check, not TD's compiler: every TD
claim below is a `LIVE CHECK`. `test_splat_render.py` still passes; BL's shader preprocesses to identical code.

**Wave 2 (27 Oct, b5 then main JazibTD_home.614): shared /project1/effectors in every module (no cap), light module
+ Lights page, Palette page + colour sources, volumetric haze + bloom v2, Geo page, lines layer (PX_lines inside),
8 new looks; everything new off = the v2 image bit for bit. Section "Wave 2" at the end.**

**Splats finished (27 Oct, splat lane, b5 then main JazibTD_home.516, b4-findings fix JazibTD_home.524): every module, effector and look verified on
real Gaussian splats; PX rests in main on the default 4-module stack over a splat scene. See "Verified live (splats)"
and "Rest state in main" at the end.**

## v2: what the Ruben Fro / reference study asked for (BR 4c "What PX must add") and where it is

| Item | Done as | Where |
|---|---|---|
| A1 point-set effector `pts` + per-point velocity | kind `pts` (a Null places/scales a CHOP / SOP set, `Ptssource`), kind `actor` (actor points from the state texture); nearest or density distance, nearest point's velocity; brute force <= 4096 points in the pass | px_common `pxPtsNear`, px_rt `effectors`, `_pts_source` |
| A2 motion paths | Effector page on every object: `Motion` line / circle / lissajous / chop / wander / follow, `Mperiod` (s per cycle: 18 s front = a par), `Mphase`, `Mloop` loop / pingpong / once, `Mease`, `Ma` `Mb` `Mfreq`, `Mchop`, `Mfollow` + `Mlag`, `Mplay`; writes the object's translate | px_logic `motion_pos`, px_rt `_move` |
| A3 falloffs behind / ahead / wake + trail | shapes 6 behind, 7 ahead (front through the centre, perpendicular to the motion; `edge` = leading-edge width x radius), 8 wake (tube along the trail ring buffer, fading with age); `Trail` (0..64) + `Traildt` per effector | `pxFront`, `pxWake`, `trail_push` |
| A4 actor layer | Source page `Actor*`: file / sequence folder / generator / depth, own transform + spin, `Actorfollow` an effector (walks a motion path), `Actorcount` ids after the scene, `Actorsamples` for the actor effector | px_source `pxActor`, px_rt `load` / `_actor_tick` |
| A5 effector glow | `Glow` (default off), `Glowcolour`, `Glowintensity`, `Glowsize`, `Glowtrail`: each glowing effector is an additive 3D Gaussian of its own shape (plane = thin beam) drawn into out1 by the reused splat shader (`px_glow_adapter.glsl`) | `glow_rows`, `glowgeo` / `glowmat` |
| A6 camera effector | kind `camera` = the output camera: position + forward as the axis | px_rt `effectors` |
| B prox_stretch | `axis` velocity / view / world x y z / effector / radial from effector / radial from camera, `mode` stretch / lattice / slices, `gap`, `bandwidth` | px_modules prox_stretch |
| B prox_burn | `source` scan / effector volume / surface, Source page `Pool %`, `rate`, `cone`, `speed`, `lifespan`, `keep` (ember keeps the source colour) | prox_burn (pool branch) |
| B twist | `mode` twist / bend (arc-length bend, curvature = twist), axis `view` (all axis menus) | `pxBend` |
| B header `chunk` | every module: points of one rest cell share id / seed / p0 and move by the cell's displacement (tiles, slabs) | px_logic `block` |
| B sprites cube / quad, Grade flare | `Sprite` cube (ray-cast box impostor, oriented, shaded), quad (world-space slab, oriented); Grade `Flare` (16-tap streak + up to 6 ghosts) | px_vert / px_pixel, px_post |
| S1 real anisotropic splats | `Render` auto / sprites / splats: sort_keys -> TOP to POP -> Sort POP (BL's route, gated) -> BL's splat MAT through `px_splat_adapter.glsl`; re-sort every `Sorteveryn` frames while centres move, on camera moves (BL's gate) | `_sorter`, `_sort_gate`, adapter |
| S2 opacity / scale / SH0 | splat alpha = look alpha (every dissolve / fade), scale x look size, dissolve flattens the normal axis (peel), recolour = SH0 (PX loads splats with SH degree 0) | adapter `pxsA1` / `pxsA3` |
| S3 stretch on covariance | t0 -> M t0 with M = th (I - a a^T) + (1 + st) a a^T (stretch < 0 flattens: shards) | hook `SPLAT_HOOK_T` |
| S4 per-splat rotation | update writes q = (module rotations x rest quaternion) to state texel 4: vortex (twist mode), twist, bend, orbit, explode swirl; lattice pulls to identity; chunk shares it per cell | px_update, modules |
| S5 embers from splats | pool points render as sprites under splats (sprite range = the pool), keep part of the splat colour | `sprite_range`, prox_burn colour |
| S6 splat DOF / bokeh | footprint + (coc/2)^2, energy kept (min energy), bokeh disc + rim, depth fog | hooks `SPLAT_HOOK_COV` / `SPLAT_HOOK_PIX` |
| D presets | KANDA swipe, Hanging streaks, Alley people fire, Radial blast, Slice bike, Tile city (create the effectors they need) | px_logic `BUILTIN` |

Not built (open): a GPU distance field for point sets bigger than ~4k (the update / look passes already use all 3
inputs, T-84; a field needs a packed aux input or a 4th sampler; the actor layer is the large-set route for now, through
`Actorsamples` stride samples); TOP / POP point sets go through a TOP to CHOP / POP to SOP the user wires (no pixel reads
in Python, T-74); a line renderer (BR 4c: covered by stretch / slices).

## Files
| File | What |
|---|---|
| `builders/px.py` | builder: `build(parent)`, `panel(parent)` (separate exec, >= 5 frames later), `park(parent)` |
| `builders/px_logic.py` | pure logic (no td): module schema `MODULES`, stack edits, `layout`/`codegen` (+ chunk wrapper, slots), per-frame row packing, drives, effector matrices + settings (`EFF_PARS`), motion paths, trails, point sets, quaternions, glow rows, layers (scene / actor / pool), splat rows, sort gate, presets + `BUILTIN`, perf model, numpy reference maths |
| `builders/px_rt.py` | TD runtime (Text DAT `px_rt`): per-frame rows, rest upload (A\|B + actor), stack -> probe compile -> swap, module pages, effector objects + Effector page + motion + trails + point sets + gizmos, sort gate, presets, pulses |
| `builders/glsl/px_common.glsl` | GLSL library: hash, noise / fbm, curl, SDFs, effector access (11 rows), point sets, fronts / wake, falloffs, proximity weight, masks + layers, quaternions, bend, cone, spectrum, attractors |
| `builders/glsl/px_modules.glsl` | one `//@module <type> <update|colour>` section per module stage (30 modules) |
| `builders/glsl/px_update.glsl`, `px_colour.glsl` | stage templates (`//@DECL`, `//@MODULES` filled by codegen; `PX_STATE_TEX` for `pxStateT`) |
| `builders/glsl/px_source.glsl` | source stage: file (rest_files A\|B) / generator / depth, morph A -> B, actor layer, pool |
| `builders/glsl/px_vert.glsl`, `px_pixel.glsl` | sprite GLSL MAT: instanced quads, size by depth, DOF CoC, streaks along velocity or a world axis, shapes incl. cube impostor + oriented quad |
| `builders/glsl/px_sortkey.glsl` | sort keys (P, id per texel) for the TOP to POP |
| `builders/glsl/px_splat_adapter.glsl` | PX side of the reused splat shader (attributes from PX textures, S2-S6 hooks) |
| `builders/glsl/px_glow_adapter.glsl` | effector glow through the same splat shader |
| `builders/glsl/px_layers.glsl` | splats + sprites (pool, glow) composite |
| `builders/glsl/px_post.glsl`, `px_trail.glsl` | grade (+ flare, one compute) and trails (one compute) |
| `builders/splat_render.glsl` | BL_splat_render's shader: + 5 hooks, empty by default (BL compiles to the same code; preprocessed text identical) |
| `builders/glsl/px_glow.glsl` | glow (bloom): ONE 7x7 compute at 1/8 res on a mipmap-filtered Resolution TOP, added in post (v1 live fix; replaces the stock Bloom TOP) |
| `builders/px_checks.py` | live checks inside TD (v1): setup/check per module vs `px_logic.ref_*`, module sweep, moving Nulls, stack-edit swap counter, preset morph sampler, perf |
| `builders/px_looks.py` | v1's 5 Ruben-Fro-like starting looks (core + stack + animated effectors), `apply` / `store` |
| `test/test_px.py` | offline tests (v1 + v2) |

## Network (left to right, every multi-pass stage is a compute GLSL TOP: T-46/T-47)
```
in_depth/in_video (DC_depth_cam out_depth + out_video) -> in_depth_pack (compute: rgb colour, a nearness)
rest_files (A|B file rest images) / rest_actor (actor file or sequence frame)       in_mask (any TOP)   in_ctl (audio)
        \___________________ source (ONE compute: A/B file|gen|depth, morph, actor layer, pool) -> rest (4 texels/pt)
state_fb (Feedback) / state_init -> update (ONE compute, GENERATED) -> look (ONE compute, GENERATED)
     eng_g/eng_e/eng_m Script CHOPs = uniform arrays uG[24] uE[88] uM[n]; eng_pts/eng_ptsv/eng_trail = texture buffers
sprites: pgeo (1 quad x drawn) + pmat + glowgeo/glowmat (effector glow) + pcam -> render
splats:  update -> sort_keys -> sorter/ (sort_pts TOP to POP -> sort Sort POP by sort_cam -> sort_sel -> sorted)
         sgeo (instances sorter/sorted, custom attr pid) + smat (px_splat_adapter + splat_render.glsl) -> srender
         layers (compute: srender + render (pool embers, glow)) ; sw_render: render | layers (eng_info splat)
sw_render -> trail (compute, Trails) -> glow_in (1/8 mipmap) -> bloom (ONE compute glow, Bloom > 0) -> post (ONE compute: + glow,
         grade + flare, uQ[10]) -> out1
effectors/ (E1 box, E2 null ...) + gizmos/ + pgeo_prev/pmat_prev (decimated, all ids) + pv_cam -> render_preview -> out_preview
```
Inputs are all optional. GLSL TOPs get exactly 3 wired inputs (T-84/T-88): source = rest_files, rest_actor, depth;
update / look = state, rest, mask. That is why A and B share one rest image (B = rows side..2 side-1).

### Texture layouts (rgba32float, point id = y * side + x, side = ceil(sqrt(Count)))
| Texture | Width | Texels per point |
|---|---|---|
| rest (`source`) | 4 * side | p0.xyz + valid, colour rgba, splat scale xyz (0 = plain point: sprites ignore it, splats use Look Size), quaternion wxyz |
| state (`update`) | 5 * side | P (visible) + age, o (offset) + life, v + heat, masks m0 m1 m2 (pool: spawn colour) + dissolve, **q (final orientation wxyz)** |
| look (`look`) | 3 * side | rgb (HDR, emission applied) + alpha, size x stretch iso isosize, stretch dir xyz + thin |
| sort_keys | side | P this frame + id (-1 for pool / unused) |

**Layers** (uG[21]): ids [0, NSCENE) scene (A/B), [NSCENE, +NACTOR) actor, the rest = pool (Pool % of Count). Header
mask input `scene` / `actor` / `pool` limits a module to one layer. Pool points are not pulled home and are visible only
while alive (age < life); dead pool points sit at the bounds centre with alpha 0.

Motion model: `home` starts at the rest position each frame; **kinematic** modules move `home` (wave, twist, bend,
orbit, explode, push "displace"...), **force** modules add to `acc`; the core integrates `o` with spring to home
(x (1 - dissolve); 0 for the pool), damping, drag, optional max speed, a NaN guard, and writes `P = home + o`. Kinematic
rotations also multiply `qrot` (S4): q = normalize(qrot x rest q), pulled to identity by `qid` (lattice).

## Codegen (one compute pass per stage, recompiled only when the STACK changes)
* **Module = data**: `px_logic.MODULES[type]` = stages + param schema; its GLSL = the `//@module <type> <stage>`
  section(s) of `px_modules.glsl`. Snippets use `$param`; the block header gives `G` (amount x mask input, inverted if
  asked), `EM` (effector bit mask), `SLOT` / `NSLOT` (index among enabled instances of the same type: the pool is split
  by id between several prox_burn) and the **chunk** wrapper. `check_snippets` (tested) proves every `$token` is a param.
* **Stack** = table `px_stack` (uid, type, enabled, label); order = execution order.
* **layout(stack)**: each ENABLED instance owns rows of `uniform vec4 uM[]`: **2 header rows** (amount, effector mask,
  mask input, invert), (chunk, 0, 0, 0), then scalars packed 4 per row (+ one `<name>ph` per `rate` param), xyz/rgb a row.
* **chunk** (header, 0..2): inside the block `id`, `seed`, `p0`, `P` are the rest cell's (cell of p0, size chunk); in
  the update stage `home` moves to the cell centre before the module and back after, so every point of a cell takes the
  cell's displacement (and rotation): tiles / slabs move in groups. chunk 0 = v1 behaviour exactly.
* **codegen** / **structure hash** / **probe swap**: as v1 (values, drives, effector links, chunk = uniforms: never
  recompile; a changed structure compiles on 8x8 probes first, live after a clean check 3 frames later).

## MODULE LIST (30; U = update stage, C = colour stage)
Every proximity module also has: radius, falloff exp, falloff shape [smooth / linear / gaussian / step / shell / core /
**behind / ahead / wake**], combine across effectors [max / sum / product / screen], flip (far = 1), ragged edge noise +
freq, space [current / rest], **edge** (front leading-edge width x radius). Every module has the header: amount (0..4),
mask input [none / m0 / m1 / m2 / visible / dissolved / heat / **scene / actor / pool**], invert, **chunk**, effectors
(names, space separated), drive (`param:src*gain+offset ...`). Axis menus everywhere gain **view** (camera forward).

| Module | Name | Stage | Effectors | Params (slider ranges; no clamps) |
|---|---|---|---|---|
| `prox_push` | Proximity push / pull | U | yes | strength -10..10; mode [displace/force]; dir [outward/centre/axis/tangent/**velocity** (stir: per point for point sets)]; publish |
| `prox_vortex` | Proximity vortex | U | yes | strength -30..30; pull; lift; mode [force/twist] (twist also rotates splats) |
| `prox_dissolve` | Proximity dissolve | U | yes | threshold; soft; noisescale; noisegain; release; curl; curlscale |
| `prox_burn` | Proximity burn / ignite + embers | U+C | yes | rise; flamefreq; flamespeed; lift; embers; consume; heatscale; ramphue; emission; **source [scan/volume/surface]; rate 0..20 /s; cone 0..180 deg; speed 0..20; lifespan 0.05..20 s; keep 0..1** |
| `prox_magnet` | Proximity magnet to shape | U | yes | pull; shell; jitter |
| `prox_stretch` | Proximity stretch / lattice / slices | U+C | yes | stretch 0..50 (splats: x (1 + stretch), < 0 flattens); thin; snap; cell; tint; tintamt; **axis [velocity/view/x/y/z/effector/radial_eff/radial_cam]; mode [stretch/lattice/slices]; gap 0..1; bandwidth 0.001..5** |
| `prox_scale` | Proximity size / alpha | C | yes | sizegain; alphagain; cull |
| `prox_colour` | Proximity colour | C | yes | mode [tint/replace/ramp/hue/invert/emissive]; colour; colour2; emission; flicker; hueshift |
| `curl` `wind` `attractor` `jitter` `glitch` `audio_displace` `shockwave` | motion fields | U (shockwave U+C) | as v1 | unchanged |
| `orbit` | Orbit / spin | U | centre/axis | as v1 (+ rotates splats) |
| `twist` | Twist / bend | U | centre/axis | axis [x/y/z/effector/**view**]; twist (bend: curvature rad/unit); wobble; wobblespeed; **mode [twist/bend]** |
| `explode` | Explode / reassemble | U | centre/axis | as v1 (+ swirl rotates splats); **auto [off/loop/pingpong], rate Hz, automax** (28 Oct, "Progress: manual, drive or auto") |
| `wave` | Wave | U | centre/axis | axis [x/y/z/effector/view/radial] |
| masks, dissolves, `lifetime` (not on the pool), `density`, `colour_ramp`, `colour_adjust`, `velocity_streak` | | | | as v1 (`dissolve_gradient` axis gains view; radial / custom shifted); `dissolve_noise` / `dissolve_gradient` gain auto / rate / automax (28 Oct) |

Core pages (COMP pars) add to v1: **Source** `Actormode` [off/file/gen/depth], `Actorfile`, `Actorseq` (folder of
frames, max 300), `Actorfps`, `Actorcount`, `Actorgen` + `Actorgenp/p2/p3`, `Actorspin`, `Actorscale`, `Actorrot`,
`Actoroffset`, `Actorfollow` (effector name), `Actorup`, `Actorcolmode`, `Actorcolour`, `Actorsamples` (actor effector
stride samples), `Pool` (% of Count for embers); **Look** `Sprite` + cube / quad, `Render` [auto/sprites/splats],
`Splatthr`, `Splatlowpass`, `Splatscalemult`, `Sortmode` [auto/always/frozen/off], `Sorteveryn` (2), `Sortmovedeg` (1),
`Sortnow`; **Grade** `Flare`, `Flarethr`, `Flarestreak` px, `Flareghosts` 0..6, `Flaredisp`, `Flaretint`.

## Effectors (objects in the scene, up to 8, table `px_eff`: name kind path prefix; wave 2: + the shared /project1/effectors list, no cap)
* Kinds: box / sphere / plane / capsule / torus = **Geometry COMP** with a unit wire shape; **Null** = point; **chop** =
  `in_eff` channels `<prefix>tx ty tz (sx)`; **pts** = a Null that places / scales a point set (`Ptssource`: a CHOP with
  samples = points (tx ty tz / x y z / P0 P1 P2) or one sample of `<name>tx/ty/tz` triples (landmark CHOPs), or a SOP's
  points, stride-subsampled to `Ptsmax`); **actor** = the actor layer's points (no object; centre = actor offset, gizmo);
  **camera** = `pcam` (axis = its forward). Stack page: Effector kind + Add effector object / Remove (Effname).
* **Effector page** (custom pars on every object effector, made by `px_rt.eff_page`): Motion..., Trail / Traildt,
  Glow..., Ptssource / Ptsmode [nearest/density] / Ptsradius / Ptsmax. Motion time = sim time (Play / Speed apply,
  COMP Reset restarts paths and clears trails). Presets store these settings.
* uE rows (11 per effector): inverse matrix 3, (sdf type, size), (centre, scale), (axis, speed), (velocity, pts start),
  (pts count, mode, trail start, trail count), world matrix 3. Velocity = frame difference of the centre (units/s); point
  sets carry per-point velocities (CHOP / SOP: frame difference; actor: the actor offset's velocity).
* Point sets: `pxPtsNear` loops over <= 4096 points (all pts effectors share the `uPts` texture buffer, `PTS_MAX`); the
  actor effector reads `Actorsamples` actor points from the state texture with a stride. Gradient = away from the
  nearest point; `pxEVel` = the nearest point's velocity. Cost: ~n x points per weight call (perf model `pts`).
* Preview: as v1; gizmos for null / chop / pts / actor. `out1` has no gizmos; glow is opt-in light.

## Splats (S1-S6, binding requirement 6)
`Render` auto picks splats when the A file loads through the splat loader (.splat / .spz / INRIA .ply). Path: `update`
-> `sort_keys` (compute, side x side: P + id) -> `sorter/sort_pts` (TOP to POP: rgb -> P, a -> custom `pid`) ->
`sorter/sort` (Sort POP, `ptmethod object`, `pointobj sort_cam` = BL's route) -> `sorter/sorted` -> `sgeo` (instancing
`sorter/sorted`, `instance0customx pid(0)`, 2x2 Rectangle POP) + `smat` (GLSL MAT, one DAT: `px_splat_adapter.glsl` +
`splat_render.glsl`) -> `srender` -> `layers` (+ the sprite render: pool embers + glow) -> `sw_render`.
**Sort gate** (`px_rt._sort_gate`, `px_logic.sort_due`): `sorter` is parked (allowCooking off) and un-parked only on
sort frames: data change / Sortnow / BL's camera gate (`splat_render_logic.need_sort`, `Sortmovedeg`) / every
`Sorteveryn` frames while an enabled module can move centres (`stack_moves`); `always` = every frame; `frozen` = pulse
only; `off` = no order, additive (cooked once for the pid list). Between sorts the order is the last one while positions
come live from the state texture (a stale order shows only as wrong overlap, never wrong positions).
The adapter maps BL's instance attributes to PX textures (P = state P, scale = rest scale x look size (peel: the
smallest axis shrinks with dissolve; lattice: iso blob of half a cell), rot = state q, colour = look rgb + alpha) and
fills BL's hooks: T (stretch / thin on the covariance), COV (DOF + fog), OUT / PIX (bokeh disc + rim). BL's own
uniforms come from `eng_s` (uRes z = 0: no order texture; dissolve / noise / explode / reveal / SH1 off), PX's from `uSp[4]`.
Count tiers for splats: keep <= 524 288 (Status warns); SmileyPinata (228 287) = Quality custom, Count 228287 (side 478).

## Presets (zctl-style, whole looks)
As v1 (store / recall / morph), plus: snapshots carry the effectors' Effector-page settings (`effpars`) and the effectors
they need (`make`: created when missing on recall / morph). **Built-ins** (`px_logic.BUILTIN`, added to `px_presets` at
build when missing; user presets never replaced):

| Look | Stack | Effectors |
|---|---|---|
| KANDA swipe | prox_colour ramp (behind, R 3, red tail -> cream front, sparkle edge 14), prox_scale (behind, size + alpha at the front), jitter | `Esw` plane (rz -90 = normal +x, 6 x 6) line -3 -> +3 x, 18 s ping-pong |
| Hanging streaks | prox_stretch axis y, stretch 25, thin 0.7, shape ahead, ragged edge | `Ehs` plane (8 x 8) climbing -1.2 -> 2 y in 4 s (8 s ping-pong); Sprite square, teal/orange |
| Alley people fire | prox_burn (scan, maskin scene, embers rate 3 /s cone 30 deg), prox_colour emissive on the actor, colour_ramp teal on the actor, wind buoyancy on the pool | `Ewalk` null (line, 20 s, trail 32), `Eact` actor; Actormode gen cylinder 8192, Actorfollow Ewalk, Pool 15 % |
| Radial blast | shockwave from the camera (Trig1), prox_stretch radial_cam driven `stretch:trig1*30`, explode driven `progress:trig1*1` | `Ecam` camera; Bloom 2, Flare 1, Chromatic 0.01 |
| Slice bike | prox_stretch slices (y, band 0.06, gap 0.45, snap 0.8), orbit 0.3 rad/s | `Esl` box 1.6 |
| Tile city | explode (chunk 0.25, noise dirs, progress = lfo1), jitter (chunk 0.25) | none; Sprite quad, Lfo1rate 0.08 |

## Perf (1080x1920, M1 Max, TD 31550 under Rosetta; `px_logic.perf_model` = an estimate, NOT a measurement)
Render cost from our live numbers: T-84 262k sprites 3.0 ms GPU + 1.07 CPU; T-89 200k 1.66 + 1.47; BL_splat_render
(f6ecc8f) 228 287 splats render 4.2 ms, Sort POP 3.0 ms per sort, 60.1 fps.

| Case (user targets in bold) | update | colour | render GPU + CPU | sort avg (spike) | post | total est. |
|---|---|---|---|---|---|---|
| 131 072 sprites (std) | 0.19 | 0.15 | 1.5 + 1.07 | - | 0.5 | ~3.4 ms |
| **250 000 sprites** (custom) | 0.31 | 0.25 | 2.86 + 1.07 | - | 0.5 | **~5.0 ms** |
| 262 144 sprites (high) | 0.32 | 0.26 | 3.0 + 1.07 | - | 0.5 | ~5.2 ms |
| **228 287 splats, Sorteveryn 2 (moving)** | 0.29 | 0.23 | 4.2 + 1.07 | 1.5 (3.0) | 0.5 | **~7.9 ms** |
| 228 287 splats, sort every frame | 0.29 | 0.23 | 4.2 + 1.07 | 3.0 | 0.5 | ~9.4 ms |
| 228 287 splats, still scene + camera | 0.29 | 0.23 | 4.2 + 1.07 | ~0 | 0.5 | ~6.4 ms |
| + 512-point set effector on 131k (one prox module) | +1.7 | | | | | (brute force) |
| + actor effector, 256 samples, on 131k | +0.8 | | | | | |

Both user targets fit a 60 fps frame (16.6 ms) with the other lab COMPs parked; neither fits the 3 ms per-COMP aim
(splats alone are 4.2 ms of render, measured in BL). Levers: Sorteveryn (2 -> 4 halves the sort average), Sortmode
frozen for still looks, Previewcount, Maxpx / Size (sprites are vertex-bound, T-100), Actorsamples / Ptsmax, flare and
bloom off. Python per frame grows with effectors: motion + trail ~0.02 ms each, a pts set ~0.1 ms per 512 CHOP points
(per-channel `.vals`), a SOP set ~1 ms per 4k points (Python point loop): LIVE CHECK P-list.

## Build (live lane; scratch TD first: new op types (toptoPOP, sortPOP, texture buffers) + 15 compute TOPs, T-83)
1. `python3 tools/lane.py add /project1/lab/PX_pointfx "PX lane"`; watchdog running (T-77).
2. Scratch: `td_exec target:'scratch'` with the build line, then the panel line >= 5 frames later; `td_errors` clean.
   First shader runs (adapter + BL shader, pxPtsNear loops, cube impostor) on the scratch TD only (T-83, T-110).
3. Main TD: same two execs; `td_layout check`; `td_checkpoint {path, note}` after each verified step (T-94).
4. Live checks below; numbers -> this file, TD facts / bugs -> `LEARNINGS.md` (T-nn).
5. Save, `park('/project1/lab')`, `python3 tools/lane.py remove /project1/lab/PX_pointfx`.

## LIVE CHECK list (expected numbers from `px_logic` references; read `out_state` / `look` / `source` / `sort_keys` with
`numpyArray(delayed=True)` in a separate exec >= 2 frames after any change, read twice and keep the second, T-74/T-91)

### v1 checks (still valid; layouts updated)
| # | Check | Setup | Expected |
|---|---|---|---|
| X1 | build + compile | `build()`; `td_errors` | no errors; `Status` "live: 4 modules, ..." after ~3 frames; `px_rows` = layout rows of the default stack (2 header rows each) |
| X2 | GLSL facts | errors of source / update / look / post / pmat / smat / glowmat on 31550 | compile clean: `uTDOutputInfo` in compute, uniform arrays + **vec4 texture buffers** from CHOPs, int bit ops, `const vec3[9]`, `isnan/isinf`, interface-block `flat` members (pmat), GLSL `#define` of `TDInstanceCustomAttrib0..6` after a call to the real one (smat) |
| X3 | generator sphere | A gen sphere size 1, B off, Actormode off, Pool 0, Quality std, read `source` | 1452x363 rgba32f; 131 072 valid texels; max \|p0\| = 1.0000 (+-1e-5) |
| X4 | id <-> texel order | texel (0,0) / (4,0) of `source` vs `ref_gen('sphere', [0,1], n)` | equal within 1e-5 |
| X5 | torus morph | B gen torus 1 / 0.3, Morph 1, Stagger 0 | every point: sqrt((\|xz\|-1)^2 + y^2) = 0.300 (+-1e-4) |
| X6 | push (displace) | A plane size 1, sphere effector r 0.5 at origin, prox_push strength 0.4 radius 1 falloff 1 smooth | point nearest (1,0,0) moves to x = 1.1989 (+-1e-3); max displacement 0.4000 |
| X7 | relink without recompile | `M1effectors` E1 -> E2 -> E1; also `M1chunk` 0 -> 0.2 -> 0 | no compile spike, `px_hash` unchanged |
| X8 | add / remove / reorder / duplicate | Stack page pulses | one recompile each; wrong code keeps the old shader ("compile FAILED") |
| X9 | dissolve_noise | sphere 131k, progress 0.25 / 0.5 / 0.75, dissolve = state texel 3 .w, Disrecover 0 | mean 0.006 / 0.442 / 0.990 (+-0.01) |
| X10 | explode | progress 1 distance 3 random 0.5 | \|P\| mean 4.00, min 2.50, max 5.50 |
| X11 | twist / wave | twist 1.3 axis y, wave sine amp 0.1 freq 3 speed 0 | radius about y unchanged (1e-4); y offset = 0.1 sin(3x) |
| X12 | spring + NaN guard | curl strength 20 then 0 | offsets < 1e-3 in ~10 s; attractor never NaN |
| X13-X22 | effector objects, CHOP effector, depth source, file + splat, presets, drives, render, perf, recompile hitch, rebuild safety | as v1 | as v1 (X16: SmileyPinata now renders as splats under Render auto) |

### v2 checks (one row per item; expected numbers from the reference functions)
| # | Item | Setup | Expected |
|---|---|---|---|
| A1a | pts from a CHOP | Constant CHOP 3 samples tx 0 0.1 0.2 (ty tz 0) as `Ptssource` of Null E3 (identity), prox_scale shape step radius 0.1 on a plane of points | a point at (0.1, 0.1, 0) has d = 0.08 (radius 0.02) -> w 1; at (0.5, 0, 0) d = 0.28 -> 0; `eng_pts` 3 samples, `uE[3*11+7].x` = 3 |
| A1b | per-point velocity | animate sample k's tx at 1, 2, 3 units/s; prox_push dir velocity strength 0.1 | push direction = the nearest point's velocity: (2,0,0) at (0.1, 0.1, 0); `eng_ptsv` rows = (1|2|3, 0, 0) |
| A1c | landmark layout | FT_face_track CHOP (one sample, `<lm>tx/ty/tz` triples) as Ptssource | point count = landmarks (<= Ptsmax); gizmo at the Null |
| A1d | density mode | Ptsmode density, radius 1, 2 points at x 0 / 1, probe at origin | d = -ln(1 + e^-0.5) = -0.3741 (inside) |
| A1e | cost | Ptsmax 512, 131k points, one prox module | update +~1.7 ms (perf model), real fps with others parked >= 58 |
| A2a | line path | Esw plane Motion line -3 -> 3 x, 18 s ping-pong linear | tx at t = 0 / 4.5 / 9 / 13.5 / 18 s: -3 / 0 / 3 / 0 / -3; espd = 0.667 units/s |
| A2b | circle / lissajous / wander / follow | circle radii 1.5 x z: \|(tx, tz)\| = 1.5 always; wander: within A +- B; follow lag 0.3 s reaches the target within 1e-4 after 5 s | as stated |
| A2c | CHOP path | 3-sample CHOP (0,0,0) (1,0,0) (1,1,0), once, 2 s | at 1 s (1,0,0), at 2 s (1,1,0) |
| A3a | behind | plane moving +x at 0.667 u/s, R 3, falloff 1.5, edge 0.03, probes at x -0.75 / -1.5 / -3 / +0.03 / +0.06 (front at 0) | w 0.6495 / 0.3536 / 0 / 0.7407 / 0.2593 (R 3 edge 0.09) |
| A3b | ahead | same, shape ahead, mirrored probes | same values mirrored |
| A3c | wake | null moving -x, trail 8 samples 0.5 apart, ages 0.25 k s, R 0.3, falloff 1 | w at (-1,0,0) 0.75, (-1,0.15,0) 0.375, (-2,0,0) 0.5, (-3.9,0,0) 0.025, (-1,0.4,0) 0 |
| A3d | trail buffer | Trail 8, Traildt 0.05, effector moving | `eng_trail` 8 rows, ages spaced >= 0.05 s, head = current centre |
| A4a | actor generator | Count std, Actormode gen cylinder 8192, Pool 15 | layers (103 219, 8 192, 19 661); actor texels follow Actoroffset; `NSCENE` = 103219 |
| A4b | actor follow | Actorfollow Ewalk (line path) | actor centre = Ewalk centre (1 frame lag) + Actoroffset; ACTORVEL = its velocity |
| A4c | actor sequence | Actorseq folder of N ply frames, Actorfps 24 | rest_actor re-uploads when the frame index changes (k = floor(t 24) mod N); no upload otherwise |
| A4d | actor as effector | Eact kind actor, Actorsamples 256, prox_burn on the scene | heat rises within radius of the actor points; update +~0.8 ms at 131k |
| A5 | glow | Glow on a plane 6 x 1 x 6 (Glowsize 1, intensity 2) | `eng_glow` rows: P (0,0,0), sigma (1.5, 0.01, 1.5), q of the plane, colour (2, 1.2, 0.5); a thin beam of light in out1, nothing in out1 with Glow off |
| A6 | camera effector | Ecam camera, shockwave centred on it | uE centre = pcam position, axis = its forward (`CAMFWD` equal) |
| B1 | stretch axis | prox_stretch axis y, stretch 25, Size 0.01 | streak screen length = 2 x projected 0.25 m, capped by Streakmax; look texel 2 = (0,1,0, thin w) |
| B2 | lattice | mode lattice cell 0.1, snap 0 (= 1) on a sphere 131k | 1889 distinct snapped positions (ref); state q = identity where w = 1; look iso = 1, isosize 0.05 |
| B3 | slices | sphere 131k, mode slices y band 0.06 gap 0.45 snap 1, w = 1 | 34 distinct y planes; fraction hidden 0.449 (+-0.01) |
| B4 | burn pool | Pool 15 %, prox_burn source volume (sphere effector), rate 3, cone 30, speed 1.5, lifespan 2.5 | alive pool fraction -> 0.88 at equilibrium (L r / (1 + L r)); spawn dirs within 30 deg of the axis (mean angle ~20 deg); dead embers alpha 0; scan source: alive fraction = 2.5 x 3 x p / (1 + ...) with p = burning share |
| B5 | twist bend | twist mode bend, axis view, twist 0.5 | a point 2 units down the view axis moves to the arc: e.g. axis -z, (0,0,-2) -> (0, 0.919, -1.683); arc length kept |
| B6 | chunk | explode chunk 0.25 | every point of a 0.25 cell has the same displacement (spread < 1e-5) |
| B7 | sprites cube / quad | Sprite cube / quad, twist on | cubes shaded per face and turning with the twist (state q); quads = slabs, edge-on = thin |
| B8 | flare | Flare 1, Flarethr 1.5, Flareghosts 3 on a bright emissive point | horizontal streak +- Flarestreak px, 3 ghosts mirrored through the centre; Flare 0 = image identical to v1 grade |
| S1a | splat path | A SmileyPinata.spz, Quality custom Count 228287, Render auto | `eng_info` splat 1; `sorter/sort_pts` 228 484 points (478^2); sorted order = BL R2 (adjacent inversions <= 0.05 %); `sgeo` instances 228 484; image = BL_splat_render's at the same camera (PSNR >= 35 dB, modules off) |
| S1b | TOP to POP / instancing facts | | `input0attrscope P` + `input1attrscope pid` map rgb -> P and a -> pid (else note the working par names in LEARNINGS); `instance0customx pid(0)` resolves; the setup notes in `sorter`'s comment are empty |
| S1c | sort gate | camera still, no moving module | `sorts` stays; orbit 10 deg/s: a sort each ~1 deg; twist on: a sort every Sorteveryn frames; Sortmode always: every frame; sorted POP keeps feeding sgeo while `sorter` is parked (P9: if not, Sortmode always and note it) |
| S2 | opacity / scale | dissolve_noise progress 0.5 on the splat scene | splat alpha = look alpha (half of them ~0), dissolving splats flatten (peel) and shrink by Dissize; recolour (prox_colour) changes SH0 only |
| S3 | stretch on covariance | one splat sigma (0.02, 0.02, 0.005) at 4 m, fy = 1000, stretch 4 along x | 2D sigma 5.03 px -> 25.0 px along x, 5.03 across; thin 0.5: 3.17 across; stretch -0.9: 0.74 px (shard) |
| S4 | rotation | twist 1.3 on the splat scene | state q = rotation about y by 1.3 x height (x rest q); lattice: q -> identity |
| S5 | embers from splats | Alley people fire on SmileyPinata | embers are sprites (render, pool range only), colour = 30 % source splat colour + fire ramp |
| S6 | splat DOF | Aperture 20, Focus 1, splat at z 4 | coc 15 px; footprint sigma^2 + 56.25; alpha x sqrt(det0/det1) (coc 10: 0.503, coc 20: 0.202 for sigma 5.03 px); defocused splats show a disc + rim |
| D1-D6 | built-in looks | Presetname each built-in, Recall | effectors created (Esw / Ehs / Ewalk + Eact / Ecam / Esl), one recompile, look as described in the table; Morph to between two built-ins over 4 s without errors |
| P1 | perf: 250k sprites | Quality custom 250000, default stack, others parked, pane elsewhere, out1 pulled | ~5.0 ms est.; real fps 60 (record update / look / render / post ms) |
| P2 | perf: SmileyPinata splats | 228 287, default stack + twist (moving), Sorteveryn 2 | ~7.9 ms est. (render 4.2 + sort 1.5 avg); real fps 60; record the 3 ms sort spike frames |
| P3 | Python per frame | 4 effectors with motion + trail, 1 pts set 512 | px_rt.frame() <= 0.8 ms (record) |
| P4 | texture buffers | `uPts` vec4 texturebuffer from eng_pts (4 channels) | `textureSize(uPts)` = sample count; fallback if refused: uniform arrays (cap Ptsmax 1024) |
| P5 | in-place mode | Statemode inplace with an actor effector | runs; actor reads race within the dispatch (one-frame jitter at most) |

## Known risks / open points
* Untested on 31550: everything in this file. Specific: TOP to POP attribute mapping par names (guarded, notes in
  `sorter`'s comment), Sort POP on a TOP-to-POP point set, instancing a POP inside a parked COMP (P9), vec4 texture
  buffers from CHOPs, `#define TDInstanceCustomAttribN` over TD's functions, toggling `allowCooking` from a Script CHOP
  cook (the sort gate runs inside `frame()`; move it to a `run()` if TD objects), `wireframeMAT` / `bloomTOP` par names.
* Point sets > 4096 points need a GPU distance field (not built, see above). A SOP point set is read in Python (slow
  above ~4k points: use a SOP to CHOP).
* Under splats the sprite render draws only the pool; the preview always shows all points as sprites.
* Effect order matters: masks before the modules that read them; chunk on a pool-spawning prox_burn shifts its spawns.

Sources: our own research files above; techniques are standard (curl noise: Bridson et al. 2007; strange attractors:
public maths; split-tone / ACES fit: Narkowicz 2015; 3D Gaussian splatting projection: Kerbl et al. 2023 via our
BL_splat_render; Barr 1984 bend; Shepperd 1978 quaternion from matrix). No code copied.

## v1 live results (26 Oct 2026, TD 2025.31550, M1 Max, Rosetta; scratch TD first, then main)
GPU numbers are readbacks >= 2 frames after the change (scratch: synchronous; main: delayed, read twice) compared with
the float64 maths in `px_logic` (`px_checks.check`). Effector rows for the reference come from the running `eng_e` CHOP.
| Check | Result |
|---|---|
| X1/X2 build + compile | 104 ops, `td_errors` clean on scratch and main; all stage shaders + probes compile (`uTDOutputInfo`, 3 uniform arrays, int bit ops, isnan) |
| X3 sphere | 131 072 valid, max \|p0\| 1.0000003, sum (-0.00027, 0, -0.00045), max err vs `ref_gen` 4.2e-7 |
| X4 id order | row 0 = bottom (numpy row 0): err 4.2e-7; flipped rows would be 1.99 |
| X5 torus morph | tube radius 0.2999995..0.3000003, err vs ref 5.8e-7 |
| X6 push displace | nearest (1,0,0) -> x 1.1989, max 0.4000001, mean w 0.72938; rms err vs `ref_push_displace` 5.5e-6 (max 2.8e-4 at the centre: numeric SDF gradient) |
| 3 moving Nulls (main) | N1-N3 on Lissajous paths, espd 0.50-0.76 u/s; frozen: 70 455 points moved, max 0.324, max err vs CPU (max-combine, best-effector direction) 7.0e-6, rms 1.2e-6 |
| X9 dissolve_noise 0.5 | mean 0.44215 vs ref 0.44215, max err 1.2e-5 |
| dissolve_gradient 0.5 | mean 0.5000001 vs 0.5, max err 3.1e-7 |
| X10 explode | \|P\| mean 4.0015, min 2.5000, max 5.5000; err vs ref 1.1e-6 |
| X11 twist + wave | radius err 2.4e-7, y = 0.1 sin(3x) err 1.4e-7, full err 2.9e-7 |
| module sweep (all 30, scratch) | every module alone: compiles live, 0 NaN, measurable effect (or none where none is expected: mask_image without a mask, velocity_streak with no motion) |
| prox_magnet | pull 1, radius 2: points land on the box surface, mean \|sd\| 8e-6 |
| X7/X8 stack edits (main) | relink 0 shader swaps; add / add / duplicate / move / toggle / toggle / remove / fix = exactly 1 swap each; bad GLSL: "compile FAILED, old shader kept", 0 swaps |
| X21 edit hitch (main) | 40-144 ms per edit (probe compile + live compile). Was 181-1194 ms until the zkit panel rebuild became lazy (only when the controls window is open) |
| X16 files | nike.splat 0.14 s, hornedlizard.spz 0.51 s (131 072 resampled); the lizard splat has 8 % of points on a sky shell at r ~ 200 (hidden in looks by mask_attr radius + colour_adjust alpha) |
| X17 preset morph | same stack (scan_morph_a -> b, 4 s smooth): values follow smoothstep(t/4) within one frame, 0 shader swaps; different stacks (dissolving_scan -> hand_push_cloud, 3 s linear): 1 swap at the start, values linear |
| X20 perf (main, pane off the COMP, out1 pulled, other lanes cooking) | named-op sum per frame, look hand_push_cloud (4 modules, glow on): draft 65k 6.3 ms (render 2.3), std 131k 7.4 (render 3.5), high 262k 9.0 (render 4.8), **ultra 1M 17.2 ms (render 11.7, update 0.87, look 0.63)**; engine Python 1.2-1.4 ms (0.72 ms for frame() alone after par caching, was 1.05); glow 0.6 ms (stock Bloom TOP was 1.7-3.2 ms at any resolution). Project real fps (wall clock, same minute): 46.3 with PX parked, 43.2 with PX std on (other lanes were already holding the project under 60) |

**Over the 3 ms budget:** even draft is ~6 ms. The instanced quad render is the floor (vertex / CPU-draw bound, as
T-84/T-100); 1M points is a show tier with the rest parked (~17 ms). Levers: Quality draft, density module, Bloom 0,
Previewcount, and the future point-sprite path (`docs/FUTURE.md` candidate). Viewing the COMP in the pane also cooks
`render_preview` (~3 ms): look at out_preview only when placing effectors.

Live fixes made during the build: Script CHOP engine rows froze (no cook per frame) -> `Frame` par bound to
absTime.frame; pcam <-> eng_cam cook loop -> camera pose + view-proj computed in Python (`px_logic.cam_viewproj`);
`stack_watch` DAT Execute did not fire for Python edits -> `write_stack` compiles itself; scan bounds stayed in file
space -> `px_logic.place_bounds`; splat loader returned `(fmt, raw)`; module state reset loses bounds -> self-reload;
stock bloom -> glow pass. LEARNINGS T-113.

## Looks (presets in `px_presets`, definitions in `builders/px_looks.py`)
| Preset | Ruben Fro reference | Stack | PNG |
|---|---|---|---|
| dissolving_scan | L6 edge fray / L1 | dissolve_gradient (x, warped, progress = lfo1 drive, re-forms) + curl + colour_ramp by dissolve + velocity_streak; nike.splat | output/px_looks/01_dissolving_scan.png |
| hand_push_cloud | L5 proximity | curl displace + prox_push force (N1 N2 N3, gaussian, publish m0) + prox_colour ramp + velocity_streak; generated ball | 02_hand_push_cloud.png (+ 00_preview_3_nulls_push.png, gizmos) |
| ember_splat | L4 fire walker | crop (mask_attr + colour_adjust) + prox_burn (sphere effector W1 walking, consume) + wind buoyancy + velocity_streak, trails; hornedlizard.spz | 03_ember_splat.png |
| scan_morph (+ _a / _b) | morph between two scans | crop + colour_ramp by height + jitter; A nike, B lizard, Morph 0.5, height stagger, arc 1.6 | 04_scan_morph.png |
| lattice_collapse | L7 lattice / streaks | prox_stretch snap lattice (N1 N2) + glitch + colour_adjust red | 05_lattice_collapse.png |

## v2 live results (26 Oct 2026, TD 2025.31550, M1 Max, Rosetta; scratch TD first, then main)
Method: `builders/px_checks.py` `v2_setup` / `v2_check`: one prox_push (displace, outward, rest space, strength 0.2), so
the GPU weight is |P - p0| / 0.2, compared with px_logic's float64 refs fed with the uniforms the GPU saw (eng_e,
eng_pts, eng_trail). Main: Play off before the delayed reads, read twice (T-91). 262 144 / 131 072 points.

| Check | Result (main; scratch the same to 1e-7) |
|---|---|
| X6 push (regression) | nearest (1,0,0) -> 1.1989, max 0.4000001, rms err 6.4e-6 (v1: 5.5e-6) |
| module sweep (30, scratch) | each module alone compiles live, 0 NaN, expected effect |
| A1a pts from a CHOP (3 points) | uE row 7.x = 3, type 6; max err 2.8e-7, rms 2.0e-8 (14 765 points weighted) |
| A1d density | max err 3.3e-7 (5 419 weighted) |
| A1b per-point velocity | eng_ptsv = (0,0,0) (1,0,0) (2,0,0) for points moving at 0 / 1 / 2 u/s: exact |
| A1c FT_face_track out_pts | 348 landmarks (2D x/y pairs, z 0 - added to `pts_from_chans`), max err 3.6e-7 |
| A1c BO_particles state | TOP to CHOP (`crop full`, `singleset`) 16 384 -> stride 512: max err 1.9e-7 (BO parked: its state was static) |
| A1c mesh (Sphere SOP 530 pts) | stride 512, max err 3.8e-7 |
| A2a line path | espd 0.667 u/s (6 u / 9 s), front centre follows Ma -> Mb |
| A3a behind / A3b ahead | max err 2.8e-7 / 2.7e-7 (83 781 / 118 798 points weighted) |
| A3c wake | trail 7 rows, ages 0.1 s apart; max err 2.2e-7 |
| A4a actor generator | layers (103 219, 8 192, 19 661); actor cylinder r 0.45, y +-0.9; 8 192 valid |
| S1 splats | after the TOP-to-POP fix (T-131): sorted POP 228 484 points, pid 0..228 286, P = state P; SmileyPinata renders as real anisotropic splats (`scratch_srender.jpg`, photographic like BL's) |
| S2 / S3 / S4 on splats | dissolve_noise 0.5 peels/fades; prox_stretch y 6 / thin 0.5 stretches the covariance into streaks; twist 1.3: state q vs the rotation measured from positions, median 1 - |dot| 1.6e-4, |q| = 1 +- 1.3e-7 |
| Built-in looks D1-D6 | recalled on `media/demo/splats/truck.splat` (Tanks and Temples truck, SOURCES.md) as points: captures `output/px_looks/v2/*_NNN.jpg`, sheets `sheet_r3*.jpg` |
| P1 250k sprites | PX 18.6 ms median (render 8.4, eng_info Python 3.3 / 2.5, glow 0.83, post 0.43, update 0.36, look 0.33); real 13 fps: 6 TDs + GEN_sim / FX_scope live on main |
| P2 228k splats + 5 modules (twist) | PX 27.3 ms median: srender 11.0, Sort POP 4.8 per sort (sorts gated: 90 in ~4 s), layers 2.4, eng 3.3; real 2 fps with 1.3 s spikes under the same load |

Not met: requirement 10 (std <= 4 ms, high <= 6 ms, 228k splats at 60 fps). These numbers were taken while other lanes
built on the main TD and 5 side TDs ran (real fps 13 even before PX's own cost); BL measured 4.2 ms for the same splat
render on a quiet machine. Re-measure with the other TDs closed before tuning; the Python engine (eng_info 2.5-3.3 ms)
is the clear PX-side lever (move to expression / one tiny Script CHOP).

v2 live fixes: TOP to POP config (rgba custom, one `r g b a -> P pid` block), sort cam / camera effector from the
engine's camera numbers (no pcam reads), point-set source resolved relative to the effector object, 2D / r g b /
P_0..2 point layouts, numpy-free CHOP stride subsample, sprite `Ptopacity` / `Ptcut`, load `Clip` / `Opacitymin`,
prox_colour `cover` (solid bands), built-in looks applied as whole looks and refreshed on build. LEARNINGS T-131.

### Built-in looks (truck scan as points, 262 144, 1080x1920)
| Look | Reads like | Capture |
|---|---|---|
| KANDA swipe | cream-white front, red tail behind it, the scan's own colour further back (KANDA 25-45 s) | kanda_swipe_330.jpg |
| Hanging streaks | square-sprite streaks hanging from the roofs, retracting top-down (geronimo 0-4 s) | hanging_streaks_040/110/200.jpg |
| Alley people fire | a sparkling person-sized actor walks the scene, the scan burns orange around it, embers rise (ALLEY 0-9 s) | alley_people_fire_300.jpg |
| Radial blast | Trig1: warp streaks to the vanishing point, then a white-hot burst (sur.render 8-12 s) | radial_blast_015/035/060.jpg |
| Slice bike | horizontal bands with gaps inside the box (DR1 80-85 s) | slice_bike_090.jpg |
| Tile city | the scan breaks into chunky slabs (VN4); drift is slow (Lfo1rate 0.08) | tile_city_100/250.jpg |

## Perf pass (26 Oct 2026, TD 2025.31550, scratch TD with 5 other TDs busy; PX perf lane; LEARNINGS T-143)
Method: PX loaded from main (`PX_src.tox`), the original beside it as `PX_old`; alternate the two (the other parked,
pane off the COMPs, out1 pulled once per frame after the engine tick, 120 frames each, 2 rounds) and report the sum of
per-op median ms (cpu + gpu, ops cooking on > half the frames) + the sorter average. Real fps of the scratch TD was
8-23 throughout, so every number is ~2x a quiet machine (T-133 (8)); the before / after ratio is the result.

| Case (look) | before (PX_old) | after | engine Python before -> after |
|---|---|---|---|
| std 131k sprites (KANDA swipe on truck.splat, moving plane effector) | 8.9-10.9 ms (comp median 13-15) | 6.6-7.3 (9.4-10.2) | 2.8-3.4 -> 0.32-0.34 |
| high 262k sprites (same) | 11.1-13.0 (16.6) | 7.3-9.1 (9.5-12.8) | 2.9-3.3 -> 0.30 |
| 228k splats (SmileyPinata, 5 modules incl. twist) | 23-27 + sort 3.8-5.2 avg | 11.7-16.9 + sort 2.4-3.2 avg | 3.5-4.1 -> 0.40 |
| engine, nothing moving | | 0.21 | |
| stack edit: add module / remove / live swap | add ~0.4 s (watchers off = the old engine, same TD; v1 on a quieter main: 40-144 ms per edit) | 0.3-0.5 s / 0.13-0.26 s / 12-30 ms (seen shader), 80-120 ms (new shader); 4.6 s before the watcher pause | |

What changed (commits b1279e8, cee7bb2, 0b89a3e + this doc):
* **Event-driven engine** (`px_rt` "per frame"): pars, module values and effector settings are cached and patched by
  `px_dirty` / `eff_watch` (Parameter Execute, expressions included) and `eff_tab_watch` / `stack_watch`; `px_tick`
  (Execute DAT, frame start) runs `frame()`; only time-dependent parts are recomputed (clock, drives, moving / CHOP /
  point-set / actor / camera effectors, rate phases, orbit, spins); only engine CHOPs whose rows changed cook (their
  constant `Frame` is bumped); eng_g is the one clock CHOP; numpy channel copies. Non-clock CHOPs never read absTime
  (T-143 (1)). Effector velocity uses the time since that effector was last read.
* `source` reads static uniforms (`eng_gs`, `eng_ez`): it cooks on load / spin / morph / depth only (0.45 ms/frame).
* Render: `glowgeo` only while an effector glows (0.75 ms); splats with no pool / glow show `srender` directly
  (sw_render input 2: sprite render + layers never cook, ~1.3 ms); post / trail sizes from Resx/Resy (a size read
  cooked the render, T-143 (3)); grain seed from a post expression (`uQf`), so eng_q is static; vertex early-out for
  dissolved points; points at rest keep their streak axis (T-143 (7)).
* Splat sort: gate counts engine frames + `Sortmaxhz` (Look page, default 20 sorts/s; 0 = no cap; pulse / data
  change ignore it). Sorter config untouched (T-124).
* Par watchers paused while module / effector pages are made (T-143 (4)).
* Tried and dropped (no gain in same-minute A/B): 256 quads per instance, a per-point sprite prep compute pass, a
  compute glow downsample (T-143 (6)).

**Still over target, and why:**
* std <= 4 / high <= 6 ms: what is left is TD's fixed cost per op under this load: the sprite Render TOP (1.7-1.9 ms CPU
  + 1.3-2.7 GPU, triangle-setup bound: 0.66 ms with nothing drawn), post 0.6 (0.34 of it is Flare 0.3 in this look:
  Flare 0 is the lever), update 0.55-0.8, look 0.35, glow 0.4, engine 0.3. On a quiet machine (BL / v1 numbers ~1/2)
  std is ~4 and high ~5 ms: re-measure on main with the other TDs closed.
* 228k splats at 60 fps: `srender` (BL_splat_render's shader, not PX's) is 7-12 ms here with this close, DOF-heavy
  camera (BL measured 4.2 ms quiet); the Sort POP is 2.2-2.7 ms per sort (avg 1.3 at 30 sorts/s, 0.8 at the 20/s
  cap at 60 fps). Further sort savings need a sorter change (e.g. sort keys at lower precision / a GPU radix sort):
  offline proposal only, T-124.
* 1.3 s spikes seen on main: not reproduced on scratch after the sort-gate fix (worst frames 31 ms srender, 12 ms
  sort). The big stalls measured were stack edits (4.6 s with the watcher, fixed) and first-time shader compiles
  (80-120 ms, up to ~1 s for the first compile of a module after a reload).
* Stack-edit hitch < 30 ms: not reachable on 31550: TD custom-par creation is ~30 ms per par on this COMP under load and
  a new shader compiles 80-120 ms synchronously. Value edits / effector relinks / preset morphs within one stack: no
  hitch. Open: reuse module pages instead of creating pars.

Export for main: `output/transfer/PX_pointfx.tox` (scratch PX after the pass, KANDA swipe look on truck.splat, high,
as loaded from main). An existing PX on main can also take the pass without a rebuild: `perf_upgrade()` in
`builders/px.py` (texts, engine CHOPs, source uniforms, watchers, render / switch expressions; never the sorter).

## Verified live (splats) (27 Oct 2026, TD 2025.31550, b5 + main; b3 verify lane for modules 16-30)
Method: `px_checks` splat helpers (`SPLAT_SCENE`, `splat_base`, `splat_sweep`, `v2_setup(..., splat=True)` / `v2_check`,
`a5_glow`, `a6_camera`). Scene = TD's SmileyPinata.spz, Quality custom 228 287 (side 478), Render splats, camera
Camdist 1.3 / Camheight 0.15 / Fov 55; one box effector E1 (tx 0.25, size 0.5). Each module alone, 30 frames, then the
textures + `srender` (1/8 grid) vs the no-module baseline + an out1 capture (`output/px_looks/splats/mod_NN_<type>.jpg`).
Every case: `eng_info splat` 1, sw_render 2 (or 1 with glow / pool), 0 NaN, real anisotropic splats in the capture.

| Check | Result |
|---|---|
| PX (Render splats, no modules) vs BL_splat_render, same scene + camera (BL: external camera = PX pcam, SH 0, no thinning, brightness / gamma 1, no sRGB) | **PSNR 73.2 dB**, max abs diff 0.061, 0.002 % of pixels > 0.02; rgb mean 0.0773 / 0.0773, alpha 0.1311 / 0.1311 (`cmp_px.jpg`, `cmp_bl.jpg`) |
| centre move: prox_push / prox_vortex / prox_magnet / attractor / explode / wave / curl / glitch / jitter | disp max 0.43 / 1.19 / 0.45 / 0.31 / 2.25 / 0.10 / 0.058 / 0.45 / 0.086; image diff 0.12 / 0.20 / 0.073 / 0.074 / 0.11 / 0.038 / 0.014 / 0.068 / 0.027 |
| covariance stretch / shrink: prox_stretch (4, thin 0.5), prox_scale (1.5), density | look stretch mean 3.95; size mean 2.48; size 0.30 (alpha 0.16) |
| opacity dissolve / peel: prox_dissolve, dissolve_noise / gradient / time, lifetime | dissolve 1.0 -> alpha 0, size 0.3 (peel); 0.043 / 0.46 / 0.37; alpha 0.20 |
| SH0 recolour: prox_colour replace, colour_ramp, colour_adjust, prox_burn, shockwave | rgb change 1.18 / 0.24 / 0.59 / 0.047 (heat 0.48) / 0.46; alpha unchanged |
| per-splat rotation: prox_vortex twist, orbit, twist | state q vs rest q: mean 170 / 20 / 13.5 deg (no rotating module: 0.01) |
| DOF (S6): Aperture 20, Focus 1 | image diff 0.061, coverage 0.131 -> 0.151, energy 7518 -> 6028 (min-energy clamp) (`s6_dof.jpg`) |
| masks (region / image / attr), wind (all-zero defaults), velocity_streak (no motion) | masks write m0 only (image unchanged alone; with a consumer: b3 table); wind and velocity_streak: no change, as expected |
| effectors box / sphere / plane / null (prox_push displace, rest space, R 0.3, linear) | GPU weight vs `ref_prox_w`: max err 3.0e-7 / 3.3e-7 / 2.1e-7 / 1.5e-7 over 228 287 splats (226 764 / 224 116 / 223 391 / 105 639 weighted) |
| point set (pts CHOP, 3 points) | uE type 6, count 3; max err 2.4e-7 (186 824 weighted) |
| path (Null line -0.5 -> 0.5, 6 s ping-pong) | velocity row -0.3333 u/s exactly while pulled; weight max err 1.4e-7 (a read after the pulls stop sees the last cooked rows) |
| wake (trail 8, 0.1 s) | trail ages 0, 0.1 .. 0.77 s; matches ref (the effector was outside the scene: 0 weighted) |
| actor (gen cylinder 6144, Eact) + prox_burn on the scene | layers (222 143, 6 144, 0); heat max 7.4, image diff 0.18; actor drawn as splats (plain points, sigma = Size / 2) |
| **A6 camera effector** (orbit 10 deg/s) | uE centre = eng_cam position (1.03366, 0.15, 0.78839), err 0; axis = forward (-0.79512, 0, -0.60645), err 3.4e-8 |
| **A5 glow** (plane 6 x 6, intensity 2) | eng_glow rows P (0,0,0), sigma (1.5, 0.01, 1.5), q (1,0,0,0), colour (2, 1.2, 0.5, 0.99) = the A5 numbers; sw_render 1 (layers), layers rgb mean 0.274 vs srender 0.061; Glow off: 0 glows, sw_render 2, identical to srender |
| modules 16-30 (b3 lane) | all pass: `docs/builds/px_splat_verify_b3.md` |

Notes from the b3 lane (documented, not changed): dissolve_time with Disrecover 0 removes the scene for good (set
Disrecover > 0 to re-form); velocity_streak streaks force-mode motion only (curl / wind / release), not kinematic
jitter / glitch; mask modules only write a mask (pair them with a colour / dissolve module); dissolve_noise progress
depends on noise scale vs scene size (0.5 dissolved 4 % of SmileyPinata: raise `scale` for small scenes; scaling the
noise by the bounds is open, it would change every stored look).

### Looks on splats
Every look has a splat version, `<look> (splats)` (`px_logic.SPLAT_LOOKS` / `splat_presets`, installed by
`install_builtins`, refreshed on build like the built-ins): the scene (truck.splat, 524 288 splats, Render **splats**,
camera as the v2 looks; ember_splat keeps its own hornedlizard.spz) then the look's values. Splat tuning (b5
captures): Bright x 0.5 (the built-ins' Bright 2 was tuned for faint sprites and blew splats out), Clip 2.2 for Slice
bike / Tile city (orbit / explode swing the far scan past the camera as screen-filling splats). Built-in looks now carry
WHOLE effector settings (Effector page defaults + the look's): a glow or trail left by the previous look no longer
survives a recall (seen live: glows 1 in every look after splat_showcase). `splat_showcase` = KANDA swipe on truck.splat
as splats with the swipe plane glowing (Glowsize 0.15). Render auto already picks splats for .splat / .spz / INRIA .ply
sources (`render_mode`, tested); the v1 presets never stored Render, so they keep the current mode.

| Preset | eng_info (modules / splat / glows) | Capture (`output/px_looks/splats/`) |
|---|---|---|
| KANDA swipe (splats) | 3 / 1 / 0 | look_KANDA_swipe_splats_.jpg |
| Hanging streaks (splats) | 1 / 1 / 0 | look_Hanging_streaks_splats_.jpg |
| Alley people fire (splats) | 5 / 1 / 0, pool 39 322 embers as sprites over splats (sw_render 1) | look_Alley_people_fire_splats_.jpg |
| Radial blast (splats) | 3 / 1 / 0 (Trig1) | look_Radial_blast_splats_.jpg |
| Slice bike (splats) | 2 / 1 / 0 | look_Slice_bike_splats_.jpg |
| Tile city (splats) | 2 / 1 / 0 | look_Tile_city_splats_.jpg |
| ember_splat (splats) | 5 / 1 / 0 (hornedlizard.spz, std) | look_ember_splat_splats_.jpg |
| splat_showcase | 3 / 1 / 1 (sw_render 1) | look_splat_showcase.jpg; sheet: sheet_splat_looks.jpg |

**b4 looks lane findings (docs/builds/px_splat_looks_b4.md) and what changed (b5, then main JazibTD_home.524):**
* Near-camera splat fog (splats had no Maxpx cap, so a few splats at the camera filled the frame): new Look par
  `Splatmaxpx` (0 = off, BL parity): the larger 2D sigma is capped and the covariance + alpha scale by k = cap^2 / l1
  (energy kept, so near splats fade); `px_logic.ref_splat_clamp`, tested + glslc; the truck splat scene uses 48 px.
* `Ascale` now scales file splat sizes too (adapter, uSp[3].w; 1 = BL parity). `Size` stays the plain-point size
  (sigma = Size / 2): for file splats the global size knob is `Splatscalemult`.
* Splat versions are full scenes (source, Count, camera, focus / aperture, clip, Render): nothing inherited from the
  look before. Recall removes the effectors the PREVIOUS recall created and this look does not need (`px_made`, user
  effectors never removed): after KANDA -> Slice bike -> Alley -> Radial the list was E1 E2 + the current look's only.
* truck.splat (2.54 M splats) now loads at the 524 288 splat cap (Quality custom), Clip 3 (was high 262 144, Clip 6:
  holes + oversized survivors); ember_splat (splats) Aperture 2 (DOF discs cost srender 5-10 ms).
* Captures after the fix: `look2_*.jpg`, `sheet_splat_looks2.jpg` (crisp truck, no fog).
* Not changed: the v1 presets dissolving_scan / hand_push_cloud / scan_morph / lattice_collapse have no splat version
  (they render on splats as stored; b4: want Bright x 0.5, lower Aperture; scan_morph mixes two files' splat scales).
* **Splats cost ~4-12 ms more than sprites** under load (b4: srender 3-10 ms GPU + Sort POP ~2 ms per sort).

Open: splat cost with 0 / 3 / 6 modules (item 5 of the splat brief) was skipped at the user's request (27 Oct, "too
late"); last numbers are the Perf pass above. PX effectors are still capped at 8 (`MAX_EFF`) and recalls add the
effectors a look needs without removing others: after 6 looks the list is full (remove unused ones by hand).

## Rest state in main (27 Oct 2026, JazibTD_home.516; re-applied with the b4 fixes in .524)
`px.rest_state()`: the builder's DEFAULT_STACK (prox_push, curl, prox_colour, dissolve_noise; effectors E1 box + E2
null, both linked) on TD's SmileyPinata.spz (Quality custom 228 287), **Render auto (resolves to splats)**, Look /
Grade defaults, `Presetname` = `default`, stored as preset `default`; `px_presets` = 22 (13 earlier + 7 splat versions +
splat_showcase + default). Recall `splat_showcase` or any `(splats)` preset from the Presets page. Parked (costs nothing
until turned on). Layout: `px.relayout()` re-flowed the COMP by STAGES (the perf-pass ops in Controls / 2 Engine, the
old stage_Other box removed) and laid out `sorter` (positions only, its config untouched, T-124). BL_splat_render points
here (comment + read-only `Splatfx` par on its Effectors page, `px.bl_pointer()`). Existing PX COMPs take this without a
rebuild: un-park, >= 2 frames, `splat_upgrade()`, then `rest_state()`, `relayout()` in separate execs (T-146).
Library copy: needs truck.splat (media/demo, git-ignored) and research_src samples (nike / hornedlizard) on this Mac.

## Wave 2 (27 Oct 2026, TD 2025.31550; RUBENFRO_COVERAGE wave 2: lines, haze, glow, colour, lights, geometry)
User (27 Oct): "everything Ruben Fro does", "green lines", "volumetric haze nd glow", "ability to change colors",
"place lights geometry in 3d space and it should effect the splats". Built on the wave-1 parts (W1-A lights,
W1-B palette, W1-C PX_lines, W1-D haze + bloom v2, W1-E geometry) inside PX. **Every new part is off by default and
out1 is then the v2 image bit for bit** (live W2-0, below). Existing PX COMPs take it without a rebuild:
`wave2_upgrade(step)` in `builders/px.py`, one step per exec: `texts`, `engine`, `stages` (recompile through the
probes), `post` (bloom v2 + haze), `geo`, `lines`, `finish` (watchers, built-in looks, re-layout); then `panel()` in
its own exec. Offline: `test/test_px_wave2.py` (22 tests) + `test_px.py` (99). Live checks: `builders/px_w2_checks.py`.

| Part | What | Where |
|---|---|---|
| 1 Shared effectors (K37) | every module's `effectors` text takes PX's own names (bit mask, up to 8 as before) AND the shared list `/project1/effectors` (`names`, `#tag`, `all`; no cap, packed buffer `uEffRows` = Select CHOP `eff_in`); module header = 3 rows: (amount, own mask, mask in, invert), (chunk, tag mask, all, on), (4 shared ids). Shared rows weigh with the MODULE's falloff (radius, exponent, shape, ragged edge) x the row's gain; fronts / wake work from the row velocity (no trail for shared rows: wake = tube behind the motion). List edits (add / rename / tag / toggle) re-pack rows only (Listver), never recompile | px_common `pxEWsh`, `pxW` 2nd loop, `pxFirst`, module-facing `pxX*`; px_logic `split_effectors` / `shared_sel` / `pack_module_rows` |
| 2 Light module (L1 / L2) | module `light` (colour stage): `effectors` = a selection of light effectors (default `all`); rgb = mix(col, col x (ambient + gain x sum lights), relight) + add x sum; emit (HDR, blooms); models half-Lambert / Lambert / wrap / glow (no normal), Blinn spec; normal auto = splat smallest-scale axis (state rotation x rest scale) for splats, glow-by-distance for plain points, or view / radial / up; light colour source (the light's own colour = default, solid tint, palette at pos, index: light k = stop k). **Lights page**: Addltype / colour / intensity / position + Addlight (a light effector in /project1/effectors, tag px; adds a light module when the stack has none), Lightinfo | px_modules `light`, px_common `pxeLightShadeB`, px_rt `add_light`; ref `px_logic.ref_light_module` |
| 3 Palette (CO2-CO5) | **Palette page**: Palsource (W1-B stops / Lospec / custom `Palstops` hex [pos] / file), Palmode gradient / steps / cycle, Palinterp, Palreverse, Palshift + Paldrive (manual / bpm step / bpm cycle / audio / onsets, Palevery, Palgain) -> `uPal[16]` + `uPalCtl` (eng_pal / eng_palc) in the colour stage, bloom, haze and PX_lines. Colour sources: `prox_colour` colsrc (palette / attr = by weight / index), `colour_ramp` ramp = palette + attribute `luma` (acid remaps, CO3), `prox_burn` firesrc = palette (fire + embers), Edge / Haze (flat Grade haze) / Flare / Glow (effector glow, index = glow k) colour sources (CPU, `scalar_colours`), Bloom colour source (GPU, px_bloom) | px_modules, px_logic `palette_spec` / `scalar_colours` / `glow_recolour`, px_rt `_palette` |
| 4 Haze + bloom v2 (H1-H3, GL1) | **Haze page** (Vh*): volumetric height fog + drift, in-scatter of up to 8 selected light effectors (`Vhlights`, default all), screen-space shafts; quarter / half res compute (`haze`, input = 1/4 of the trail output, mipmap) composited in `px_post` (input 2, uQh; no extra op). Depth: none (scene alpha = object distance). **Bloom v2** replaces px_glow: same defaults (diff 0), + Bloomknee, Bloomtight (1/4 scale, `glow_q`), Bloomclamp, Bloomtint + Bloomsat, Bloom colour source, ring halo (Bloomring, radius, width, chroma) | `_haze`, `_bloom_v2`; px_haze.glsl / px_bloom.glsl (W1-D) |
| 5 Geo page (GE1 / GE4) | Geoon, Geocomps (any Geometry COMPs), Geolights (`#light` = the light effectors) + Geokey, Geodepthbias; **Geoadd** (box / sphere / torus / plane / tube + PBR colour / metallic / roughness / emission) makes objects in `geo/`. One Render Pass chain: geo_render (geometry, depth write) -> geo_pass (splats, depth test on / write off) -> geo_spass (sprites, pool embers, effector glow) -> geo_out; occlusion both ways; emission blooms in PX's bloom | `_geo`, px_rt `add_geo` / `geo_lights` / `geo_sync`; W1-E `geo_stage` |
| 6 Lines (G1-G6) | **Lines page** Lineson (+ Linesdepth: hidden behind Geo geometry via `lines_depth`); PX_lines is built INSIDE PX (`PX_lines`, its own pages: rings / contour / trails / connect / polyline / edges): in1 = the scene (alpha occlusion + edges), in_points = `update` (Ptstride 5, Ptcount = count), Camera = pcam, Palette = PX's (linked); Outmode composite = scene + lines in one compute, before trail / bloom / haze, so the HDR lines glow | `_lines`, `sw_lines` |
| 7 Looks | 8 built-ins (whole scenes, below); presets also carry `lights` (light effectors made in /project1/effectors, tag pxpreset; the previous look's are removed), `geo` (objects in geo/), `lines` (PX_lines values; the rest back to defaults). User Store keeps PX_lines' changed values | px_logic `BUILTIN`, px_rt `_apply_w2` |

### Wave-2 looks (built-ins; captures `output/px_w2/looks/`, sheet `sheet_w2_looks.jpg`)
| Look | Scene | Shows |
|---|---|---|
| Green line sweep | truck.splat | neon-green contour lines scrolling across the dimmed scan (Bgdim), a green front sweeping it (prox_colour behind + glowing plane), palette neon_green, tight bloom |
| Neon rings | SmileyPinata | 6 rings expanding + orbiting (tilted), one palette stop per ring, a stop on every beat (Paldrive bpm_step), bloom ring halo |
| Haze shafts | truck.splat | two coloured spot light effectors: beams + lit fog (Vh), the scan relit by the same lights (light module) |
| Light sweep | truck.splat | a warm point light travels along the street (expression on its tx) and reveals the dark scan (relight 1, ambient 0.05) |
| Lit splats + geometry | SmileyPinata | a metallic sphere + an emissive green ring among the splats (occlusion both ways), magenta / cyan lights relight splats and geometry alike |
| Palette beat cycle | truck.splat | height ramp through the rainbow palette turning a full cycle every 4 beats, edge lines in the same palette |
| Acid palette | SmileyPinata | brightness remapped through the acid palette (colour_ramp luma) |
| Fire clouds | truck.splat | the scan burns near a wandering volume, big ember pool in fire-palette colours rising (wind + curl), warm haze, a fire light |

### Verified live (wave 2) (27 Oct 2026, TD 2025.31550; build TD b5 with main's PX + /project1/effectors loaded read-only, then main by builder)
Method: `builders/px_w2_checks.py` (snap / diff of out1 numpy captures, shared / light / palette checks vs the float64
references, haze dump vs `px_haze_logic.ref_haze` offline, per-op cost via `px_checks.ab_start` / `pair_ab` with the
network pane off the COMP). Scenes: plane of points (131 072, std) and SmileyPinata splats (228 287), Play off and
displace modules in rest space for the diff checks (a current-space displace iterates P frame to frame, T-178 (5)).

| # | Check | Result |
|---|---|---|
| W2-0 | out1 with every new feature off vs v2 (same COMP, before / after the upgrade, same sim time), Bloom 0.8 | sprites: **diff 0** (8.3 M values), splats: **diff 0**; update / look textures identical. Needed: own-effector GLSL untouched (a branch inside moved P by 5e-6, T-178 (1)) |
| W2-1 | shared selection, prox_push displace (R 0.3, linear) on the plane: `box1` / `#demo` / `all` | GPU weight vs ref max err 3.3e-7 / 3.7e-7 / 4.3e-7 (44 812 / 61 074 / 85 258 points weighted); header rows (0, 0, 1) + ids (2, 0, 0, 0) for box1; list edits / selection changes: 0 recompiles (px_hash constant) |
| W2-2 | light module vs `ref_light_module` (4096 probes) | points, 1 point light, glow model: 6.0e-7; point + spot + area + directional, half-Lambert + spec, palette index colours, add 0.3: 4.9e-6 (values ~3); splats (smallest-axis normals from state q + rest scale), point + spot: 4.9e-6 - 7.7e-6; capture `w2_light_splat.jpg`; Addlight pulse: light effector made + a light module added, Lightinfo "3 lights on" |
| W2-3 | palette | colour_ramp palette by height (fire, oklab) vs `pal_eval`: 1.5e-6; luma attribute, acid, steps + shift 0.34: 0.0; Paldrive bpm_step at 120 bpm: shift 0.34 / 0.673 / 0.007 per beat, px_hash constant (no recompile); Edge palette 0.5 / Haze index 2 / Flare palette + keep 0.5 = pal_eval / pal_step / mix exactly (uG[10], uQ[5], uQ[8]) |
| W2-4 | bloom v2 + haze | bloom legacy defaults: out1 diff 0 vs px_glow (after splitting the legacy loop, T-178 (1)); haze (2 light effectors, density 0.15, shafts 0.8, noise 0): GPU vs `ref_haze` median 0.033 %, p99 0.087 % (270 x 480, quarter); Vhon off: haze never cooks, out1 diff 0 |
| W2-5 | Geo | Geoon off: diff 0 (sprites + splats); box in front: geo_spass = geo_render exactly (max 0.0) on 40 310 px, 203 px where near floor splats lie in front = splat over box (5e-4); sphere behind the pinata: out = splat over sphere within 0.007 (15 022 px behind splats with alpha > 0.95); geo_render lights = the light effectors + geo_key; capture `g_out.jpg` |
| W2-6 | Lines | Lineson off: diff 0; PX_lines in PX: rings seg vs `ref_segments` 3.2e-7; contour on the splat scene 32 768 segments, 27 valid-flag mismatches at band edges (float32 positions); capture `w2_lines.jpg` |
| W2-7 | 8 looks | each recalled on b5 (truck.splat 524 288 / SmileyPinata 228 287 splats): 0 op errors, lights / geometry / lines made and removed per look; captures `output/px_w2/looks/`, sheet `sheet_w2_looks.jpg` |
| main | wave2_upgrade texts -> finish + panels in main (one step per exec; checkpoint 1: JazibTD_home.578 after items 1-3; final: **JazibTD_home.614**) | 0 errors un-parked and parked; Lineson + Vhon on: 0 errors; PX panel 356 knobs, PX_lines panel 157; parked; library/PX_pointfx 0.3.0 |

**Cost (b5, 31550, same-minute A/B, pane off the COMP; 4-5 other TDs on the GPU, so ~2x a quiet machine):**
| Feature | Cost |
|---|---|
| everything new off vs v2 (two COMPs alternating, same scene, Bloom 0.8) | total 9.29 -> 10.04 ms median (+0.75): look CPU +0.16 (palette + effector buffer uniforms), bloom CPU +0.10 (more vec uniforms), others within noise; GPU unchanged |
| 1 shared effector (box) in one module, 228 k splats | update GPU +0.12 ms |
| light module, 3 lights, 228 k splats | look GPU +0.13 ms |
| palette colour source (prox_colour attr, oklab) | look GPU +0.04 ms |
| haze (quarter res, 2 lights, shafts) | haze 0.16 CPU + 0.21 GPU, haze_src 0.06 + 0.15 (~0.6 ms) |
| bloom tight scale + ring + palette tint | bloom GPU +0.10, glow_q 0.06 + 0.30 (~+0.5 ms) |
| Geo on, 2 PBR objects (splats) | geo_render 1.32 CPU + 0.23 GPU, geo_spass 0.38 + 0.16, geo_pass replaces srender: total +1.1 ms |
| Lines (rings 512 + contour 32 768 segments, Halo default) | PX_lines render 0.72 + 0.85, seg 0.25 + 0.13, comp 0.17 + 0.28 (~2.8 ms) |

Open (wave 2): PX_lines draws in its own Render TOP (~0.7 ms CPU floor): drawing `lgeo` in PX's render would save it
(not done: PX's sprite render does not cook under splats); the env cube (chrome reflections, W1-E Geoenv) is not wired
in PX (chrome objects reflect nothing: the Lit splats + geometry look uses a satin metal); shared effectors' trails /
glow (A3 wake trail, A5 glow) work for PX's own effectors only; PX_lines custom stops (Palsource custom) read PX_lines'
own `pal_stops` table, not PX's Palstops; haze has no scene depth (covered pixels = Vhobjdist).

## Wave 3 (27 Oct 2026, TD 2025.31550; build TD b5, then main by builder; RUBENFRO_COVERAGE wave 3)
Every feature is off by default; off = out1 diff 0 (echo code, grid section and K25 rows are only pasted / read while
used). Checks: `builders/px_w2_checks.py` (packet_check, front_check, attr_check, echo_check, blur_check, heat_stats).

| Item | What | Live result (b5) |
|---|---|---|
| SA18 packet glitch | `glitch` mode packet: per-cell rigid offset + rotation about the cell centre (splats rotate with it), reassemble envelope from the beat / trigger (`envsrc`) | rigid within 1.3e-7, 0 points moved before the hit, rotation 8.6 -> 0.06 deg as the trigger decays |
| K24 / TC-36 camera | Camera page: orbit / crane / dolly / path / follow / director (shots `crane:8 orbit:8 ...`, quantised to N beats, cut / ease / arc), roll, shake (`cam_rig_logic.py`, engine cam row tx ty tz ry rx rz, rotate order xyz) | pcam = engine row, target at NDC (0, 0); director cuts at beats 128 / 136 / 148 / 156 (quant 4) |
| K25 camera motion blur | `velocity_streak` source camera / both: apparent velocity -(CAMVEL + CAMOMEGA x (P - CAMPOS)) from uG[24..25] | crane 60 deg/s: omega 1.046 rad/s, stretch vs ref 7.9e-8, direction 6e-7 |
| SA19 / SA20 fronts | `dissolve_gradient` axis camera / spiral + linger + swirl | vs `ref_dissolve_front` 1.7e-6 / 2.9e-6 |
| SA15 splat attributes | `mask_attr` / `colour_ramp` by splat size (cbrt), opacity, flatness | mask vs ref 2.3e-6 |
| SA31 / TC-37 echoes | Echoes copies of the actor after the pool (shift register every Echoevery frames in the state feedback), offset per copy = depth stack, alpha fade | copy k = actor + (k+1) offset within 7.8e-8, alpha 0.8 / 0.6 / 0.4 / 0.2 |
| SA21 / SA5 grid | `heat_spread` module + light `bounce` through the shared voxel grid (PX's hot points -> cloud row `px_hot` in /project1/effectors; grid field on input 2 via `aux_src`, `#define PXE_GRID`) | hot radius 0.20 -> 0.42 in 7 s with spread, 0.15 without |
| K19 / K28 source top | Amode / Bmode / Actormode `top`: any points TOP (Pointstop or the in_xyz input) on input 2 | rest p0 = TOP pixels exactly (8192 valid) |
| K21 / SA35 sprites | Sprite glyph (5x5 font, 32 glyphs; cell random / luma = ascii art / time), dab (rotated bristle stroke + colour jitter), atlas (any TOP of N x N cells) | sprite shaders off-path diff 0 (old vs new texts in place); captures `output/px_w2/w3_glyph_dab.jpg` |
| SA33 kNN lace | look "kNN lace sweep": PX_lines connect (<= 4096 points, k 3) masked by a sweeping plane front | partial: no load-time index for the full cloud |
| leftovers | haze depth from the geometry (+ alpha end for splats, uH[12].w), PX_lines custom stops = PX Palstops, Fire clouds dimmer | done |

### Wave-3 looks (captures `output/px_w2/looks/`, sheet `sheet_w3_looks.jpg`)
Packet glitch, Crane director, Fire spreads, Echo dancer, Glyph city, Pointillist, Spiral reveal, kNN lace sweep: each
recalled on b5 with 0 op errors. Fixed after the first captures: Glyph city was blown out (add blend + big tiles: now
alpha, size 0.012, emission 0.4); Spiral reveal stayed black once swept (Disrecover 0: now 1.0, re-forms).

**Cost (b5, per-op cook medians over 150 frames, pane off the COMP, 4-5 other TDs on the GPU):**
| Feature | Cost |
|---|---|
| Echoes 6 (Echo dancer, 228 k splats + 6144-point actor) vs 0 | total 12.5 -> 19.8 ms: echo copies drawn by the sprite `render` (0.63 CPU + 3.9 GPU) + `layers` 0.24 + 0.43; keep Echoes for small actors |
| grid (Fire spreads: heat_spread + bounce, 524 k) | hot_pts 0.30 CPU; update 0.34 + 0.48 GPU (3 modules), look 0.62 + 0.33 |
| camera rig + K25 (Crane director) | update 0.30 + 0.42 (velocity_streak); rig maths in px_rt tick (eng_g < 0.2 CPU) |
| packet glitch | update 0.30 + 0.37 |
| glyph sprites (262 k) | render 1.5 + 5.5 (sprite pass, as other sprite shapes) |
The truck splat render (524 k, srender 17-24 ms GPU here) dominates those looks: that is the scene, not the feature.

Open (wave 3): K22 strands, K27, K36 at any count in proximity modules, K34 data -> sound; lines drawn in PX's own
Render TOP (no gain under splats); the +0.75 ms CPU with everything off (wave 2) not investigated; kNN over the full
cloud needs an index.

## Wave 4 (27 Oct 2026, TD 2025.31550; build TD b5, then main by builder; RUBENFRO_COVERAGE 64 / 3 / 0)
Every feature is off by default (Sound off, Echoes 0, Cnindex brute, no strands module, no Drivechop); off-path
checks: echo sprite shaders diff 0, source pass diff 0 (old vs new texts in place). Checks: `builders/px_w2_checks.py`
(k36_setup / k36_check) + offline dumps compared with the references in `px_logic` / `px_lines_logic`.

| Item | What | Live result (b5) |
|---|---|---|
| SA33 kNN lace, whole cloud | PX_lines `Cnindex grid`: `cn_index` (compute, one workgroup per 8^3 brick, shared uint atomicMin of (priority << 22 \| id)) = one representative point per voxel of the REST positions (PX: Cnindextop = `source`, static: indexed once per scene); each sample links to its k nearest representatives in the 27 voxels around it, drawn at the live positions | index = `ref_index` exactly (1516 / 1516 voxels, ids 100 %; 64^3: 5581 / 5581); 196 361 segments = `ref_segments` exactly; seg 0.27 + 0.38 ms for 65 536 samples (brute 4096: 0.25 + 1.96) |
| K36 / GE2 big clouds | a module whose shared selection reaches a `cloud` row compiles PXE_GRID (`stack_cloud`, re-checked on list / module edits); input 2 = the grid field | 16 384-point sphere cloud, R 0.3: every point within R - cell hit, none beyond R + cell, max error 0.77 cell |
| K22 strands | `strands` module: blade along up + curl-noise wind, length variation, by brightness, thin | stretch vs `ref_strands` 8.3e-7, direction exact (sway 0) |
| K27 image relief | Amode `image`: Pointstop / in_xyz / Imagefile picture -> relief (brightness / hue / alpha / red x Imagerelief), aspect kept | xy exact (5.9e-8), z = relief x luma of the sampled colour within 2e-8 |
| K34 sound | `sound` COMP (parked unless Soundon): 64 x 64 block sums of the state -> Analyze average -> lag -> drone (height), shimmer (speed), noise (dissolve) -> x Soundvol -> Audio Device Out on the DEFAULT output (cookalways off; no input device) | checked with the device inactive: mean speed / dissolve / height vs `ref_sound` within 1e-7, oscillator frequency / amplitude = `sound_freqs` |
| K33 control CHOP | Drive page `Drivechop`: every channel of any CHOP (OSC In / MIDI) is a drive source (`/1/fader1` -> `1_fader1`) | uM strength 0.2 + 2 x 0.25 = 0.7 |
| echoes cost | copy k draws at Echoscale^k (0.8) and keeps (1 - Echothin)^k (0.75) of its points (uR row 8) | Echo dancer, 6 echoes: sprite render GPU 5.2 -> 1.7 ms (fill was the cost: tiny sprites 0.47 ms); echoes off = diff 0 |
| +0.75 ms with everything off (wave 2) | eff_in follows eff_rows only while PX reads the list (`eff_use`, px_rt `_eff_use`), else eff_none | eff_in: 0 cooks when off (was every frame, 0.02 ms + the buffer re-upload to 4 GLSL TOPs); the other wave-2 ops cooking when off: geo_out + sw_lines 0.03 ms CPU. The rest of the wave-2 +0.75 was the busy-GPU A/B (4-5 TDs) |

Fixes found on the way: PX_lines' PX-owned pars were constants that every look recall reset (Ptstride 5 -> 1: contour /
connect read the wrong texels since wave 2) -> expressions (T-192); built-in looks left unnamed module params at the
previous look's values -> every module param written at its default first, packer tolerant during a recall (T-195).

Looks (captures `output/px_w2/looks/`): **Grass field** (K22), **Painting pillars** (K27, Starry Night, public domain,
`media/demo/paintings`, git-ignored), **kNN lace sweep** now on the voxel index (49 152 samples, 64^3).

Open (wave 4): GE3 chrome env in PX, K26 fisheye / equirect output, K32 30-160 M point scans (not real-time on this
Mac); the shared grid has one field for all cloud rows (a module selecting one cloud sees the nearest of any cloud);
PX_lines rows cook per frame while a Maskop is followed (2.3 ms CPU, W1-C).

### Wave 4b (27 Oct 2026, b5 then main): the last partials
| Item | What | Live result (b5) |
|---|---|---|
| GE3 chrome | Geo page `Geoenv` (off): W1-E `env_capture` (prox_mat.py, reused, not copied) on PX's decimated preview geometry (`pgeo_prev`, Previewcount sprites) -> 128 px cube every 4 frames -> equirect -> Cache hold -> `geo_env_light` in geo_render's lights (the lights expression reads Geoenv so it re-evaluates); "Lit splats + geometry" now uses a true chrome sphere | chrome sphere shows the scene (`output/px_w2/w4_chrome_off_on.jpg`); capture 2.4 CPU + 2.2 GPU ms on every 4th frame (~1.2 ms per frame) vs BL's full-splat capture 16 ms; Geoenv off = out1 diff 0 |
| K26 dome / 360 | Output page `Proj` perspective / fisheye / equirect: render + srender as cube maps (Projface per face, sprite / splat px sizes from the face) -> `proj_render` / `proj_srender` (Projection TOP) -> `pr_*` switches into sw_render / layers | perspective = out1 diff 0; fisheye + equirect captures (`w4_fisheye.jpg`, `w4_equirect.jpg`), 0 errors. Fisheye on a square Resx = Resy (a 9:16 frame squashes the dome); equirect 2:1. Splats are sorted for the main view: far cube faces can show order errors. Geo / Lines / Haze stay perspective only |
| PX_lines follow cost | `rows_static` (the par-driven rows, reads no world transform while following) + `rows` (copy + only the object / camera rows per frame, `px_lines_logic.rows_follow`) | kNN lace sweep: rows 2.3 -> 0.42 ms CPU per frame; rows = full rows() within 4.9e-6 |
| K32 | 30-160 M point scans | out of scope on this Mac (tiers to 4 M; decimate offline) |

Viewer note (T-143 (9)): with the network pane on PX, viewers of unpulled ops (proj_*, geo_env_cube) cook every frame;
measure with the pane off the COMP. RUBENFRO_COVERAGE after wave 4b: 66 covered, 1 partial (K32), 0 missing.

## Perf wave 27 Oct (b3)
Look page **Splataa** (srender MSAA, default 1x; aa4 = the old render, +1.3-1.6 ms GPU on 228k splats, no visible
change) and **Sorteveryn** default 6 (was 2). Existing COMPs: `perf27_upgrade()` then `panel()`. b3: 6.0-7.5 -> 5.1-5.3 ms;
why it stays over 3 ms: docs/builds/PERF_FINAL_27OCT.md "Perf wave 27 Oct (b3)". Main received it by tox bring-home
(T-212: main crashed once right after the load, the relaunched main holds the new PX, parked).

## 28 Oct changes
- `Disrecover` ("Dissolve heal /s") default **1.0** (was 0 = sticky; user: "dissolve doesnt come back"). Dissolved points
  heal at that rate whenever no module keeps them dissolved; 0 restores the old sticky dissolve.
- Refresh key: **F5** pulses `Reset` on every cooking lab COMP (`/project1/hotkeys`, `builders/hotkeys.py`; change the key
  with its `Key` par).

## 28 Oct: live dropdowns, Resolution menu, re-staged network (b3)
User: "can u not have a drop down for these? and all"; "i want a option to be able to change the render resolution and
heirarchy should folow it"; "reorganise nodes inside pointfx for cleaner readablity and heirarchy".
- **Dropdowns** (StrMenu + `menuSource` = `px_rt.menu(comp, name)`, items built from `builders/menu_logic.py` on each
  menu read, never per frame, T-233). You can still type in every field. Par names are unchanged, so presets,
  expressions and saved files still bind.
  - `Presetname`: the stored presets. Type a new name, then Store.
  - `Sel` (was Int): the stack, labelled `4 Dissolve: noise (off)`. The value is the uid as text; `px_logic.sel_uid`
    reads both old and new.
  - `Effname`: PX's effector objects. `Actorfollow` / `Camfollow`: the same, plus `(none)` (value `' '`).
  - `M<uid>effectors`, `Vhlights`, `Geolights`: helper items. `+ X` adds a name / #tag, `- X` removes a word, plus
    `all` and `(clear)`. Each item is the whole new text.
  - A parked PX shows its last items until it cooks.
- **Resolution** (Look page, before Resx / Resy): 1080x1920 (default), 720x1280, 540x960, 1920x1080, 1280x720,
  2160x3840, 3840x2160, Custom.
  - Picking an item sets Resx / Resy. Typing another size switches the menu to Custom (T-236).
  - Every screen-space TOP follows Resx / Resy, or a fixed divisor of them:
    - full size: render / srender / geo_render / proj_*, layers, trail, post, out1, PX_lines comp / render;
    - haze half or quarter, PX_lines edges by Edres, glow 1/4 and 1/8 of its input;
    - `render_preview` is now half of Resx x Resy (it was a fixed 540x960).
  - Point-state / data TOPs stay sized by the point count.
  - b3 live check: every item, 96 TOPs compared, 0 mismatches, out1 at the new size, 0 errors. `trail_fb` resizes on
    its next cook (it only cooks with Trails on).
- **Network**: stage boxes in reading order, left to right: Controls / 0 Code / 1 Inputs / 2 Engine -> 3 Source ->
  4 State + update -> 5 Sort | 6 Look / colour -> 7a-c Render (sprites, splats, geometry) -> 8a Lines -> 8b Trails +
  glow + haze -> 8c Post -> 9 Out | 10 Preview.
  - `STAGES` 'after' hints set the order. `geo_key.shadowcasters` is now `''` (shadows are off; `'*'` made the layout
    read a wire from every op). `relayout()` check is clean: 143 ops, no overlaps / back wires / intruders / unboxed.
- **Existing COMPs (main):** `oct28_upgrade()`, then `relayout()` and `panel()` (or zkit `refresh_panel`), each in
  its own exec. It changes values, presets and par order in place and touches nothing else; Resolution starts at the
  item for the current size.

## 28 Oct: presets (sweep, fixes, reorder / rename) + auto progress (b3, main's PX exported 28 Oct)
User: "can u see if presets wrok and how do i re-arrange them ... and also if all presets actually work? i just put
explode and the animaiton froze"; then "i like the progress bar too - its so i can animate it if iwant to".

### Presets: how to
All on the **Presets** page (and its zkit page). `Presetname` is a dropdown of `px_presets` in table order.
- **Recall:** pick a name, pulse `Recall`. The look's stack, values, effectors (created when missing; the ones an earlier
  recall made and this look does not need are removed), lights / geometry / lines come back. A new scene file loads
  once, ~0.2-1.7 s (one hitch frame, T-237).
- **Store:** type a new name in `Presetname` (or pick one to overwrite), pulse `Store`. Built-in names are refreshed by
  the next PX build: store an edited built-in under your own name.
- **Morph:** pick the target, set `Morphtime` / `Morphcurve`, pulse `Morphto` (`Stopmorph` stops). Same stack = every
  value lerps; another stack = the target's stack installs at once and shared modules lerp. Menus / toggles switch at
  half time; **source pars (file, count, Clip, Opacitymin, ...) switch once at the start** (T-237: before, a morph
  between two scenes re-loaded the file every frame, ~50 s frozen).
- **Reorder:** pick a preset, pulse `Presetup` / `Presetdown` (one row per pulse); the dropdown follows at once.
  `Presetsort` = A-Z, built-ins first (built-ins = the BUILTIN looks, their `(splats)` versions, `splat_showcase`).
  Only cells are rewritten in the new order: the row count never changes, nothing is deleted (a write that is not an
  exact permutation is refused).
- **Rename:** pick it, type the new name in `Newname`, pulse `Presetrename` (refused when the name exists or is empty;
  the snapshot's own name follows). A renamed built-in becomes your look; the next build adds the built-in again.
- **Delete:** `Deletepreset` (no undo).
- By hand: `px_presets` (name, json) is a plain Table DAT; its row order IS the dropdown order.
- **zkit knob window slots are separate** (`controls/zk_presets`, 8 slots, values of the panel's knobs only, not
  stacks / effectors): `+` stores in the next free slot, drag `+` onto a slot stores there, click = recall, Shift+click
  = overwrite, drag on a slot = morph to it, right-click = delete. There is no drag-to-reorder: to move slot 3 to 5,
  recall 3, Shift+click 5, right-click 3; or edit the `slot` column of `zk_presets` (rows are found by that number).

### Progress: manual, drive or auto
`explode`, `dissolve_noise`, `dissolve_gradient` are pure functions of `progress` (0..1): with nothing moving it, they
look frozen. Each now has, right after `progress`:
- `auto` [Off / Loop (0 -> top, repeat) / Ping-pong (0 -> top -> 0, eased)], `rate` (Hz, cycles per second, default
  0.1 = one 10 s cycle), `automax` (the top, default 1).
- Auto runs in the GLSL (`pg` = fract of the integrated `rate` phase, like the other rate params): no new per-frame
  Python. While auto is Off its rate costs nothing (`rate_live`).
- **A module you ADD from the Stack page starts in Ping-pong at 0.1 Hz**, so it moves at once.
- **progress stays yours:** grabbing / typing `progress`, giving it an expression, export or CHOP, or a drive on it
  (`M<uid>drive progress:...`) switches that module's auto to Off at once (`px_autoguard`, a Parameter Execute on
  `M*progress M*drive`: value / expression / export / mode events, never per frame). PX's own writes (recall, morph,
  page sync) are remembered and their late events (T-236) ignored, so a preset that says Loop stays Loop.
- Presets store auto / rate / automax and recall them exactly. Older presets (and every built-in) load with auto Off:
  their progress and drives behave as before. The user's current stack got auto Off (no change).
- Main tab: `M4progress` stays in `zk_essentials.json` (unchanged); auto / rate / automax are on the module's page tab.

### Trigger looks: Trigauto
`Radial blast` (+ splats) waits for `Trig1` (drives `stretch:trig1`, `progress:trig1`, a shockwave on trig1): frame
diff 0.0047 idle, 0.34 with a press. Drive page: `Trigauto` (s, 0 = off, default off) fires the trigger(s) picked in
`Trigautowhich` (all / trig1..4) every N s; checked on b3: Radial blast at Trigauto 2 = diff 0.15 per s, 0 = 0.027.

### Preset sweep (b3, main's 40 presets; recall, 60 settle frames, 3 s measured, out1 pulled each frame, frames read 1 s apart)
| Preset | Result | fps | alive (frame diff / 1 s) | Note |
|---|---|---|---|---|
| dissolving_scan | ok | 59.7 | 0.018 |  |
| hand_push_cloud | fixed | 60.0 | 0.084 | effectors N1-N3 were never created (no `make`); now made + moving (after: alive 0.094) |
| ember_splat | fixed | 60.0 | 0.016 | effectors W1 were never created (no `make`); now made + moving (after: alive 0.024) |
| scan_morph | ok | 59.7 | 0.095 |  |
| scan_morph_a | ok | 60.0 | 0.015 |  |
| scan_morph_b | ok | 59.6 | 0.083 |  |
| lattice_collapse | fixed | 59.7 | 0.011 | effectors N1 N2 were never created (no `make`); now made + moving (after: alive 0.018) |
| KANDA swipe | ok | 60.0 | 0.029 |  |
| Hanging streaks | ok | 60.0 | 0.158 |  |
| Alley people fire | ok | 59.7 | 0.028 |  |
| Radial blast | ok | 60.0 | 0.005 idle | trigger look: alive 0.34 with Trig1 (or Trigauto) |
| Slice bike | ok | 60.0 | 0.063 |  |
| Tile city | ok | 59.7 | 0.160 |  |
| KANDA swipe (splats) | ok | 60.0 | 0.013 |  |
| Hanging streaks (splats) | ok | 56.7 | 0.035 | heavy look (perf, not an error) |
| Alley people fire (splats) | ok | 40.5 | 0.022 | heavy look (perf, not an error) |
| Radial blast (splats) | ok | 60.0 | 0.004 idle | trigger look: alive 0.38 with Trig1 (or Trigauto) |
| Slice bike (splats) | ok | 59.7 | 0.049 |  |
| Tile city (splats) | ok | 59.0 | 0.118 |  |
| ember_splat (splats) | fixed | 59.0 | 0.009 | effectors W1 were never created (no `make`); now made + moving (after: alive 0.017) |
| splat_showcase | ok | 56.6 | 0.013 | heavy look (perf, not an error) |
| default | ok | 59.7 | 0.094 | first sweep 18.2 fps: a 6.9 s frame from the multi-load on recall (T-237); re-run 59.7 |
| Green line sweep | ok | 58.1 | 0.023 |  |
| Neon rings | ok | 60.0 | 0.097 |  |
| Haze shafts | ok | 58.7 | 0.005 |  |
| Light sweep | ok | 60.0 | 0.037 |  |
| Lit splats + geometry | ok | 29.5 | 0.004 | heavy look (perf, not an error) |
| Palette beat cycle | ok | 58.7 | 0.116 |  |
| Acid palette | ok | 59.7 | 0.007 |  |
| Fire clouds | ok | 59.7 | 0.008 |  |
| Packet glitch | ok | 58.1 | 0.020 |  |
| Crane director | ok | 60.0 | 0.041 |  |
| Fire spreads | ok | 59.3 | 0.004 |  |
| Echo dancer | ok | 59.7 | 0.022 |  |
| Glyph city | ok | 60.0 | 0.004 |  |
| Pointillist | ok | 44.2 | 0.007 | heavy look (perf, not an error) |
| Spiral reveal | ok | 59.3 | 0.018 |  |
| kNN lace sweep | ok | 54.2 | 0.040 | heavy look (perf, not an error) |
| Grass field | ok | 56.5 | 0.007 | heavy look (perf, not an error) |
| Painting pillars | ok | 59.1 | 0.034 |  |

Morph checks: `scan_morph_a` -> `scan_morph_b` (same stack, lerp): morph done, 59.8 fps, 0 errors. `KANDA swipe` -> `Green line sweep` (other stack + scene): before the fix 17.1 fps with ~50 s of frozen frames (T-237); after: morph done: Green line sweep, one 1691 ms load frame at the start. All rows 0 op errors, stack as stored, every `make` effector present. fps = b3 with every other lab COMP parked and no other build TD running (a later re-sweep with b2 + main busy read ~20-35 fps for every preset alike, the machine, not PX).

### Fixes
- `hand_push_cloud`, `lattice_collapse`, `ember_splat`, `ember_splat (splats)`: their modules named effectors N1-N3 / W1
  that only px_looks' absTime expressions created; the rows had no `make`, so after the rest state (E1 / E2 only)
  nothing pushed / burned. The rows gain `make` + transforms + a lissajous Motion close to the old expressions
  (`px_logic.V1_FIX_PRESETS` / `fix_v1_preset`, only when missing). After: N1-N3 / W1 created and moving on recall.
- Morph / recall reload storms (T-237): see above.
- Nothing else was broken: 0 op errors, every stack as stored, every `make` effector present, drives all parse and
  point at existing params (offline audit of all 40 rows).

### Existing COMPs (main)
`presets28_upgrade()` (idempotent; second run returns `changed: []`; on b3 it touched only the 4 v1 rows, kept the
40 presets, their order and every par value), then `relayout()` (places `px_autoguard` in Controls), then zkit
`refresh_panel('/project1/lab/PX_pointfx')`, each in its own exec. Tests: `test/test_px_presets28.py` (20).

## 28 Oct: beat sync + setlist (phase A, b3; main by `beatsync28_upgrade`)
User: "go for it but i like the progress bar too - its so i can animate it if iwant to". Manual control wins
everywhere: a drive on `progress` turns that module's auto off (px_autoguard), and a par you move during a transition
stays yours (below).

### Beat sync: how to
1. Turn on `/project1/lab/AU_features` (un-park; `Analysison` on for beats / onsets / tempo; its default source is the
   `kick_128bpm_30s` test file, never the mic; it creates no audio device). Bass / mid / high / level also work with
   Analysison off (they come from an FFT of AU's own audio, see docs/builds/au_features.md "Bands").
2. PX **Drive** page: `Audiosrc` = the AU_features COMP (default `/project1/lab/AU_features`; empty = off).
   `Beatsync` on = `beat`, `tempo`, the GPU beat uniforms, beat triggers and transition beats follow the audio.
3. Use the sources in any module's `drive` (`param:src*gain+offset`, as before):

| Source | What | Needs |
|---|---|---|
| `beat` | 1 on each beat, decays at `Beatdecay` /s | Beatsync on (off = PX's own Tempo / Bpm clock, as before) |
| `tempo` | phase 0..1 through each beat (`tempo` = ramp, e.g. `rotate:tempo*6.28`) | Beatsync on (off = the clock's phase) |
| `onset` | 1 on each onset, decays at `Beatdecay` /s | Analysison |
| `bass` `mid` `high` | 20-150 / 150-2000 / 2000-16000 Hz, 0..1 (dB scale, AU `Bandfloor` -> 0) | AU cooking |
| `level` | AU `loud` (LUFS 0..1) with Analysison, else the FFT full-band level | AU cooking |

   Examples: `progress:beat*1` (explode / dissolve pulses on every beat), `strength:bass*2`, `amount:onset*0.5+0.5`.
   An `Audiochop` / `in_ctl` channel with the same name (`mid`, `high`, `level`) still wins over AU's.
4. **Triggers** (Drive page): `Trigsource` manual (pulses + `Trigauto` s, as before) / beat / onset / nbeats (every
   `Trigbeats` beats); `Trigautowhich` picks which of Trig 1-4 fire. With Beatsync off, beat / nbeats use PX's clock.
- AU parked, missing, or Audiosrc empty: every audio source reads 0, nothing errors, `Status` says why (one note per
  state change: "audio: AU_features is parked (turn it on) ...", "... Analysison off: bass / mid / high / level only").
- Cost: the engine reads 9 channels of `<Audiosrc>/out_features` and runs a few lines of maths per frame, and only
  while something uses them (Beatsync, Trigsource onset, or a drive word onset / bass / mid / high / level): 0.026 ms
  (b3). No new op, no per-point Python; the driven values reach the GPU in the existing `uM` rows (eng_m).
  If PX reads AU first in a frame, AU's own cook (1.3-1.5 ms on b3, it costs that anyway when on) is counted in
  PX's tick: px_tick median 0.50 ms without audio -> 2.0-2.2 ms with Beatsync on.

### Setlist: how to (Presets page; the presets are only referenced, never changed)
- **Order:** `px_setlist` (Table DAT inside PX, one column `name`; the `Setlist` par can point to any table) lists
  preset names in show order. **Empty = the presets table order.** `Setlistfill` copies the current presets order in,
  to edit by hand (add rows, reorder, a look twice). A name that is not a preset shows `(missing)` in the `Cue` menu
  and in Status; Next / Prev skip it, Go refuses it.
- **Play:** `Next` / `Prev` (wrap around at the ends), or pick `Cue` (dropdown `3 KANDA swipe`) and pulse `Go`.
  `Current` (read only) shows `3/12 KANDA swipe`. Next / Prev / Transition are on the zkit **Main** tab.
- **Transition:** `Transition` seconds (beats when Beatsync is on: 4 = 4 beats at the AU bpm; no bpm -> seconds),
  `Transcurve` linear / ease (in-out). 0 = cut (Recall). It is the preset Morph (Morphto) with its T-237 fix: a
  different scene file loads once at the start (one 0.2-1.7 s hitch frame), the stack switches at once when it differs.
- **Your hand wins:** a par you move (knob, typing, a script) while a transition runs keeps your value; the morph stops
  writing it until the next transition (`_morph_tick` checks each par against what it wrote last frame, T-245).
- **Hooks:** CQ_cuelist / TL_timeline set **`Cueindex`** (1-based scene number; PX goes there when the value changes,
  0 = nothing). CQ: a `par` cue, target `/project1/lab/PX_pointfx:Cueindex`, value `3`, fade 0. TL: a lane on
  `/project1/lab/PX_pointfx` par `Cueindex` with hold keys. Next / Prev never write Cueindex, so a lane that keeps
  writing its value does not undo your Next; to repeat the scene already in Cueindex, set 0 first. Any script:
  `op('/project1/lab/PX_pointfx/px_rt').module.setlist_go(op('/project1/lab/PX_pointfx'), 'KANDA swipe')`
  (a name, `'3 KANDA swipe'`, `'3'`, or a 0-based int).
- Presets never store `Audiosrc`, `Beatsync` or the setlist pars (`px_logic.NOSNAP`); `Trigsource` / `Trigbeats` are
  part of a look (a look may fire on the beat).
- Changing the table while a scene runs: `Current` keeps the old text until the next Next / Prev / Go.

### Live checks (b3, TD 2025.31550; AU_features built from its builder on b3, kick_128bpm_30s, Analysison on)
| Check | Result |
|---|---|
| `M4drive progress:beat*1`, Beatsync on (dissolve_noise, default stack), 480 frames | 32 AU beats, 32 progress pulses, 0 frames from AU's beat_count edge to progress = 1.0; intervals median 0.4667 s (128 bpm = 0.4688; AU bpm 127.66), decay 1.0 / 0.607 / 0.333 per 3 frames; b3 real fps 32 (main + b2 busy) |
| Trigsource beat / nbeats 4 / onset (AU), beat with Beatsync off (Bpm 120) | 19 of 19 beats fire all four; 5 fires on 18 beats (trig1); 17 of 17 onsets (trig2); 17 in 8.08 s; manual 0 |
| AU parked / Audiosrc empty / wrong path / Analysison off | Status notes as above; progress uniform 0.0 over 90 frames; 0 op errors; Analysison off: bass 0.62, beat / onset / tempo 0 |
| Setlist `scan_morph_a`, `nope_not_a_preset`, `scan morph B (mine)`, `KANDA swipe`; Transition 2 s linear | Next -> 1/4; Next -> 3/4 (skipped the missing name); Exposure 0.5 -> 0.9 linear (0.5867 at 0.433 s = 0.5 + 0.4 x 0.217), done in 1.95 s; Camdist 3.0 -> 2.2 |
| Beatsync on, Transition 4 (beats), ease | morph 1.92 s (4 beats at the AU bpm of that moment), curve smooth |
| Cue `4 KANDA swipe` + Go, Transition 0 | cut: stack prox_colour / prox_scale / jitter |
| Cueindex 2 -> Next -> Cueindex 2 again -> 1 | 2/3, then 3/3 (Next not undone by the unchanged 2), then 1/3 |
| hand during a 4 s transition (Exposure = 0.2 at 1.2 s) | Exposure stays 0.2 (hold), Camdist finishes 2.5833 -> 2.2 |
| presets after all checks | 40 rows, sha1 of the table unchanged |
| `beatsync28_upgrade` twice | 1st: texts, page order, 14 new pars, px_setlist, px_values Cueindex; 2nd: `changed: []`, presets 40 = 40, 0 errors |

### Existing COMPs (main), each in its own exec, pane on /project1, PX un-parked >= 2 frames before
1. `AU_features`: `bands_upgrade()` (builders/au_features.py; second run `changed: []`), then zkit `refresh_panel`.
2. Per PX (`PX_pointfx`, `PX_pointfx1`): `beatsync28_upgrade('/project1/lab', name=...)` (runs presets28_upgrade
   first; run twice, the second returns `changed: []`), `relayout(name=...)`, zkit `refresh_panel('/project1/lab/<name>')`.
Main tab (`builders/zk_essentials.json`): + Prev, Next, Transition; out: Agen, Ascale, Tealorange (still on their
pages). Tests: `test/test_px_phaseA.py` (27).

## 28 Oct: phase B, playability + safety (b3; main by `phaseB_upgrade`)
User rules kept: manual control wins, no bloat (new controls on the Stack page, Main tab unchanged at 16), nothing
removed. Tests: `test/test_px_phaseB.py` (37).

### Module browser (Stack page)
- `Addtype` is a dropdown of every module, grouped Proximity / Motion / Dissolve / Mask / Colour, each item labelled
  `Motion › Explode / reassemble — points fly out and back` (the one-line `desc` in `px_logic.MODULES`). The value is
  the module type (`explode`); typing a type, its name or a whole label also works; an unknown type goes to Status
  ("add: unknown module type ...") and nothing is added. It was a static Menu: `phaseB_upgrade` converts it in place
  (value kept).
- `Addafter` on: `Add` puts the new module right after `Sel` (off = at the end, as before). Not stored in presets.

### Solo / bypass (Stack page, acting on `Sel`)
- Bypass = the existing `Toggleon` (enable / disable). `Sel` labels: `3 Proximity colour (off)`, `5 Explode (solo)`.
- `Solo`: only the selected module runs (one recompile). Solo another module while soloed: the solo moves, the saved
  set stays the first one. `Unsolo`: the enabled set from before the first Solo comes back exactly (same shader hash).
- A Toggleon while soloed also changes that module's flag in the saved set (your hand wins). Modules added while
  soloed keep their state on Unsolo.
- Never in presets: `Store` while soloed writes the saved (real) set; `Recall`, `Morphto` and a setlist scene end
  solo (the look brings its own set). The saved set lives in the COMP's storage `px_solo`.
- Status after the recompile: `live: 1 modules, 6 uniform rows | solo M5 (Unsolo restores the set)`.

### Copies (copy-paste a PX)
- Each PX registers its hot points (heat spread / bounce grid) in /project1/effectors under its own row,
  `px_hot_<comp name>` (`px_logic.hot_key`), kept in storage `px_inst` {key, path}. Before, every PX used one row
  `px_hot`; in main that row pointed at PX_pointfx1, so the original had none. `phaseB_upgrade` renames the legacy row
  for the PX it points at; the other PX makes its own row when its grid turns on. Other PX's hot rows never count as
  selectable clouds (`stack_cloud`).
- **Paste is safe by itself**: on its first cook a copy sees that its `px_inst` names another live PX
  (`px_rt.instance_check`), takes a new row name and points every reference to the original's children at itself:
  `controls_window` winop (PX and PX_lines: the copy's Opencontrols opened the ORIGINAL's panel), both zkit `zk_cfg`
  targets (the copy's knobs drove the original), any constant string par inside it. A moved / renamed PX keeps its key
  and its row's ref follows. What it did is in `px_notes`. No Makecopy pulse was needed.
- Lights a look creates in /project1/effectors are not removed by one PX while another PX's look also made them.
- Two PX cooking at once: Status + px_notes `2 PX cooking: 2x cost (PX_pointfx, PX_pointfx1)` (checked every 60
  engine frames through a tiny shared registry, no scans per frame).
- Not PX's part: zkit's Main tab is keyed by the COMP name in `zk_essentials.json`, so a copy gets the fallback Main.
  Presets of a copy still name the original's geo objects in `Geocomps` (presets are never rewritten).

### Preset checks on recall / morph / setlist scene
Recall never raises. What could not be applied goes to Status and to the `px_notes` table (frame, kind, text; 200 rows):
`recalled X: 2 pars skipped (Bogusfoo, Oldrenamedpar); module type unknown: zap; effector missing: E9; file missing:
phaseB_test.png`. Checked: pars this PX does not have, values that could not be set, module types it does not know
(dropped), effector names a module selects that are neither PX's own nor shared rows (`all`, `*`, `#tags` are not
names), file / folder pars in use that do not exist (Afile with Amode file, Palfile with Palsource file, ...), bad JSON
(`recall failed: X: error: not a PX preset (...)`). A morph never writes pars that do not exist. A setlist scene
appends the issues to its own Status line.

### Hard size limits (T-231: Metal aborts on a texture past 16384)
Every texture PX derives stays <= `px_logic.TEX_MAX` = 8192 a side; the par keeps your value, the effective value is
used and Status says so once per change (also in the load message and px_notes):
| Par | Limit | Status example |
|---|---|---|
| Count / Quality | `COUNT_MAX` = 1638^2 = 2 683 044 points: the state texture is 5 x side wide (8190 x 1638) | `Count 80M -> clamped to 2.68M (8192 px state texture)` |
| Quality `max` (4M) | kept in the menu, runs at the cap; label `Max 4M (runs 2.68M: texture cap)` | `Quality max 4.19M -> clamped to 2.68M ...` |
| Resx / Resy | both scaled together so the larger side <= 8192 (aspect kept); every screen TOP, haze, glow, trail, preview, PX_lines follow | `Res 20000x12000 -> 8192x4915 (8192 px max)` |
| Projface, Geoenvres | cube faces <= 4096 (`CUBE_MAX`) | `Projface 9000 -> 4096 (cube faces <= 4096)` |
| PX_lines Maxseg | segment texture rows <= 8192 (Maxseg <= 2 097 152) | `Lines Maxseg 100M -> 2.1M` |
How: `px_logic.clamp_expr` rewrites `parent().par.Resx` (etc.) in PX's own TOP expressions to the clamped form (spelled
`me.parent()...`, so a second pass changes nothing); `quality_count` / `proj_res` clamp on the Python side. To allow
more, raise `TEX_MAX` (16384 is Metal's hard limit; check the margin on the target Mac first).

### Existing COMPs (main): `phaseB_upgrade` is UI-safe and staged (T-249)
b3 crashed (SIGBUS, UI thread) once during an in-place upgrade right after a big COMP copy in the visible network,
so the upgrade now: closes every PX window (controls, PX_lines controls) and floating viewers, moves every network
pane that shows the PX, its inside or its parent one level up, turns the node viewer off, and runs the work in
deferred steps 3 frames apart (texts -> menus -> tables -> done; the only par replace, Addtype, has a frame of its
own; expression edits are in place). The node viewer comes back at the end; closed windows stay closed (listed in the result as `closed_windows`):
reopen them with Opencontrols after `refresh_panel`. The call returns at once;
read the result in a LATER exec with `phaseB_result`.
Per PX (`PX_pointfx`, `PX_pointfx1`), pane on /project1, PX un-parked >= 2 frames before, each line its own exec,
>= 2 s apart:
1. `phaseB_upgrade('/project1/lab', name=...)`; 2. `phaseB_result('/project1/lab', name=...)` (state `done`,
`presets_kept` True); 3. run 1 + 2 again: `changed: []`; 4. `relayout('/project1/lab', name=...)`;
5. zkit `refresh_panel('/project1/lab/<name>')`.

## 28 Oct: phase C, speed + external camera (b3; main by `phaseC_upgrade`)
User rules kept: manual wins (the auto layer never writes a par), defaults unchanged (Autoquality off, Lod off,
Camsource internal), no bloat (one new page `Perf`, two pars on Camera). Tests: `test/test_px_phaseC.py` (34).
Numbers: b3, TD 2025.31550, fresh copies of main's 28 Oct PX (`output/transfer/PX_pointfx_main_28oct.tox`: SmileyPinata
228 287 splats, Geo on, haze on), out1 pulled, pane on /project1, every other lab COMP parked; ms = per-frame cpu + gpu
of PX's ops (PERF_FINAL method), GPU numbers swing ~1 ms between windows (other TDs on the GPU).

### Auto quality (Perf page)
- `Autoquality` Off (default) / Hold 60 fps. On: when the average fps (Perform CHOP `px_perf`, exponential average)
  stays under `Aqfps` (57) for `Aqframes` (45) frames, it steps down one step; it steps back up after 3 x Aqframes
  frames with the average frame time under `Aqheadroom` ms (10) and fps >= Aqfps. A step up followed by a step down
  within 10 s doubles the wait for the next step up (max 8x): no ping-pong. 30 frames after a step are ignored.
- Steps, mildest first: splat MSAA -> 1x (only when Splataa is above 1x and the render is splats), points 75 %, points
  50 %, then render resolution 75 % and 50 % (with points 50 %).
- **It never touches your pars.** The step lives in `px_auto` (Constant CHOP: aa, countf, resf, kside) which the
  expressions multiply in: srender MSAA, every render-chain TOP size (render, srender, geo_render, layers, trail, haze,
  PX_lines, proj_*), the sort-key texture, the sprite stride. `post` and `out1` stay Resx x Resy (post samples the
  smaller chain by uv), so nothing downstream changes size. Splataa / Count / Resx / Resy keep what you set;
  `Aqstate` (read only) shows `step 3/4: points 50%, res 75% = 810x1440 (fps 60)`, Status gets one line per step.
- Points at a step are really fewer: the sort-key texture holds ceil(N x f) keys, key k = splat floor(k / f) (a fixed
  subset, no flicker), so the Sort POP and the splat instancing get fewer points; the kept ones grow by 1 / sqrt(f)
  (Size, Minpx, Maxpx, Splatscalemult), pixel sizes follow the resolution step.
- **Governor** (`Autoquality` = Follow FG_fps_governor): the step comes from `Govop` (default
  `/project1/lab/FG_fps_governor/out1`) channel `quality` through `px_logic.gov_plan` (= `fps_gov_logic.px_plan`, tested
  equal for q 0..1): q < 0.9 splat AA 1x, < 0.8 points 75 %, < 0.65 points 50 %, < 0.5 res 75 %, < 0.35 res 50 %.
  Missing, parked or Active off = full quality + one Status / Aqstate note (`governor fg parked / Active off: full
  quality`). Checked on b3 with a stand-in CHOP: missing -> full + note; q 0.55 -> `governor quality 0.55: splat AA 1x,
  points 50%` (keys 478 -> 338, out1 1080, Resx / Splataa unchanged); Active off -> full; q 1 -> full; Off -> `off`.
  The built-in Hold 60 controller stays as the other option; both off by default.
- Checked on b3: Aqfps 61 (always under) stepped 0 -> 4 (srender 540x960, out1 1080x1920, keys 478 -> 338); Aqfps 30 +
  Aqheadroom 14 stepped back to `full quality (0/4)` (px_auto back to 1, sizes back to 1080 / 478); with Splataa aa4
  the first step is `splat AA 1x` (srender aa1, Splataa still aa4; Off -> aa4). At Aqheadroom 10 b3 held its step:
  b3's frame time with a test loop running was 10-11 ms (no headroom), which is the intended hold.
- Cost (main's PX, Geo on): full 10.2-10.6 ms; points 75 % 10.5, points 50 % 10.3 (no saving here: Geo on draws the
  splats in geo_pass, fill-bound); res 75 % 9.0, res 50 % 8.5-9.2. With Geo off, half the splat instances cut srender
  GPU 3.15 -> 1.88 ms (measured by halving the instance count, same scene).

### Splat LOD by distance (Perf page): measured, no saving, default Off
- `Lod` (off), `Loddist` (6: thinning starts there, full at 2x), `Lodkeep` (0.35). Splats (adapter) and sprites
  (px_vert) past Loddist are kept when their id hash < the share and the kept ones grow by 1 / sqrt(share).
- Result: **no measurable saving** on b3 (Geo off, 228k splats): Camdist 1.3, Lod off 6.9-7.1 ms vs Loddist 1 / keep 0.35
  6.8-7.4, Loddist 0.6 / keep 0.25 6.9-7.0; Camdist 6, Loddist 3 / keep 0.25 (most splats thinned) 7.1-7.2 vs 6.6-7.1
  off. Visibly different (frozen frame, mean |diff| 0.065, alpha coverage kept 0.890 -> 0.887). Why: the culled splats
  still run the vertex shader and BL's shader has no early exit for a per-splat alpha 0 (only its global Opacity is an
  early out: all culled that way = 1.24 vs 3.25 ms GPU); far splats are small, so their fragments were cheap anyway.
  Cutting instances is what saves (the points step above). Left Off; the lever would be an early exit inside
  BL_splat_render's shader (the other lane's file) or a compacting sort (GPU sorter changes are T-124 territory).

### Sort only on change (Perf page `Sortstill`, default on; Sortmode auto)
- The every-N-frames re-sort now runs only while something can move the centres: a module that is not still at its
  values (px_logic `STILL_RULES`: e.g. curl in force mode, jitter, lifetime, burn, any live rate, any drive), a moving
  effector, a moving source (spin, depth, actor), plus a settle time after any real value change (7.8 / (Damping +
  Drag) s, 1-8 s; 4.6 s at the defaults). Paused (Play off) an edit sorts once. A re-read after a pause / park is not a
  change. The camera keeps its own gate (Sortmovedeg / Sortmaxhz). Sortstill off = the old rule.
- Main's default stack has curl in force mode, so it keeps sorting (no change at defaults: 6.4-7.1 ms).
- A still stack (curl displace, speed 0): sorter/sort 0.68-0.77 ms per frame -> 0 (not cooking); sorts stay at 4 while
  idle. Camera move: Camdist 1.3 -> 1.6 + Camheight -> one sort (2 -> 3); its frame vs a forced Sortnow frame: mean
  |diff| 0.0068 = the frame-to-frame noise of prox_colour's flicker (0.0067 between two frames with the same order).

### External camera (Camera page `Camsource`, `Camcomp`)
- `Camsource` Internal (default: orbit / Camera rig, as before) / External; `Camcomp` = a dropdown of every Camera COMP
  under /project1 (PX's own left out), e.g. `/project1/lab/CS_cam_sequencer/cam_out`. External: PX's engine camera row
  comes from that COMP's world transform (any rotate order, parent, look-at) and its horizontal fov from its
  `projection(Resx, Resy)`; pcam (fov now from `eng_cam` channel `fov`), the splat projection, the sort camera, PX_lines
  (uses pcam), the haze and the camera effector all follow. Recomputed only when the external camera moved. Not a
  missing COMP: Status `camera: Camcomp ... is not a Camera COMP: internal camera`.
- b3 check (CS_cam_sequencer from library, shots corner1-4): Select 0 / 1.5 / 3 and Playmode sequence: pcam position =
  cam_out position to 4 decimals, forward dot 1.0, fov 45 = 45, the bounds centre projected through cam_out's own
  matrices = PX's view-projection (e.g. (0.0397, -0.2858) both); out1 mean 0.371 / 0.352 / 0.337; also with Render
  sprites + Lines on + haze (PX_lines Camera = pcam, 0 errors).
- Cost: px_tick 0.91-0.94 ms -> 1.29-1.32 with CS playing (the moving camera re-sorts and re-computes haze rows, as an
  orbit does); COMP 9.6-10.2 -> 10.2-10.6 ms.
- Camsource / Camcomp and every Perf par are never stored in presets (`NOSNAP`) and never part of a built-in look.
- zkit Main tab: `Camsource` replaces `Disrecover` (still on its page) for PX_pointfx and PX_pointfx1.

### Existing COMPs (main), first: `usecam_upgrade` (external camera only)
Phase B's steps (no-ops on a phase-B PX), px_logic / px_rt texts, Camera page Camsource / Camcomp, pcam fov from
`eng_cam`. No Perf page, no shader / op / size change; the new runtime is inert without the Perf pars (sort rule as
before, no auto quality, LOD rows 0; the 10-row uR / 5-row uSp CHOPs feed the old shaders with no warning, checked).
Same safety as below (T-249 / T-250 / T-251: windows closed, pane off, COMP not current / selected, zkit panel parked,
steps 20 frames apart, waits on a pending recompile). Per PX, each line its own exec, >= 3 s apart:
1. `usecam_upgrade('/project1/lab', name=...)`; 2. `usecam_result('/project1/lab', name=...)` (state `done`, errors 0,
`presets_kept_but_v1_fix` True); 3. run 1 + 2 again: `changed: []`; 4. `relayout(...)`; 5. zkit `refresh_panel(...)`.
Proof: b3, 2 fresh loads of the main tox (PX_u1, PX_u2) with node viewer + out1 viewer open: run 1 done in ~140 frames,
run 2 `changed: []`, 0 errors, b3 alive; PX_u1 followed CS cam_out (Select 0 / 2.5: pcam = cam_out, centre NDC equal)
and went back to its orbit camera on Internal. (A first attempt crashed b3: T-251.)

### Existing COMPs (main), then: `phaseC_upgrade` (UI-safe, staged; runs phase B first)
Steps 20 frames apart (T-250: 3 frames crashed b3 once), each waits while a stack recompile swap is pending, one
shader DAT per step, the zkit panel parked during the upgrade. Per PX (`PX_pointfx`, `PX_pointfx1`), pane on /project1,
PX un-parked >= 2 frames before, each line its own exec, >= 3 s apart:
1. `phaseC_upgrade('/project1/lab', name=...)`; 2. `phaseC_result('/project1/lab', name=...)` (state `done`,
`presets_kept_but_v1_fix` True, errors 0); 3. run 1 + 2 again: `changed: []`; 4. `relayout('/project1/lab', name=...)`;
5. zkit `refresh_panel('/project1/lab/<name>')`. Proof: b3, 3 fresh loads of the main tox (PX_t1..t3), node viewer + out1
viewer open, pane on /project1/lab: each run 1 done in ~260 frames, run 2 `changed: []`, presets kept (only the 4 v1
looks, as phase B), 0 errors, b3 alive after each. Re-proved with the final code (governor, T-251 `_ui_safe`):
PX_c1, PX_c2 loaded parked (T-254), un-parked and out1 viewer opened in later execs, a background `sample` armed: run 1
done, run 2 `changed: []`, 0 errors, no crash.

## 28 Oct: Presetsource, presets keep the imported cloud (b3; main by `presetsrc_upgrade`)
User bug: "changing a preset also changes the pointcloud or splat file that i have imported". Presets page toggle
**`Presetsource`** ("Presets change the source", default **Off**, never stored in a preset). Off: Recall / Morphto /
setlist Go / Next / Prev / Cueindex skip every Source-page par (files, modes, generators, Morph, counts, Clip /
Opacitymin, actor, image, echoes; tuplet parts too) + `px_rt.LOAD_PARS` + Camsource / Camcomp
(`px_logic.source_par_names` / `strip_source`, applied in `px_rt._load_checked`; the morph start snapshot is stripped
too), so built-in looks apply to the user's own cloud and nothing reloads. Store still records the source; On = the
old behaviour. Effectors a preset makes are still created. Status: "... | source kept (Presetsource off)" (not a
px_notes issue). Existing COMPs: `presetsrc_upgrade(parent_path, name=)` (UI-safe, staged s_texts / s_pars / done,
20 frames apart, zkit panel parked) + `presetsrc_result()` in a later exec. Proof b3 (31550, in-place on the phase C
PX): banana.ply 60000 pts imported; Recall Glyph city / ember_splat / scan_morph / Pointillist, Morphto Neon rings,
setlist Go KANDA swipe (splats): source-par hash unchanged, no load requested, looks applied (stack + grade changed);
Presetsource On -> Glyph city loaded truck.splat again; presets byte-identical, 0 errors, 60 fps; a second run
`changed: []`. Tests `test_px_presetsrc.py`.

## 29 Oct: drop-in round (lane A, b2; main by `indep_upgrade`)
User (29 Oct): "make sure everythings independent ... they should work if copy pasted in another project".
- **Hot row follows the grid:** `px_hot_<name>` (tags `pxhot pub`) is ON only while a compiled module reads the grid
  (heat_spread, light bounce: `stack_grid` with PXE_GRID compiled), OFF otherwise (`px_rt._hot_sync`, called from
  `_grid_wire` on every stack event incl. the unchanged-hash path, and once on the first cook via `hot_want`). Never
  per frame. No shared list: nothing happens, no error. b2: + heat_spread -> row made, enabled, ref = own hot_pts,
  aux_src 1; toggled off -> row `enabled 0`, aux_src 0. Being #pub, no other consumer reads it (effectors.md
  "Published rows").
- **eff_in** reads `eff_rows_pub` only while a module's shared selection names a #pub row (`eff_use` 2), else
  `eff_rows` (#pub rows inert there). `stack_cloud`: `all` no longer reaches a #pub cloud.
- **Copies:** two loads of one tox (the original's path missing here) no longer share a hot-row key
  (`instance_check`: a key held by another live PX = a copy).
- **Splat order always valid / the sgeo warning:** in sprites mode the sorter never cooked in a fresh session (POP
  data is not saved), so sgeo warned `instance attribute 'pid(0)' could not be found in .../sorter/sorted`
  (reproduced b2: fresh load, Render sprites). `_sort_prime` cooks the sorter once per session (un-park, pull
  `sorted`, parked the next frame; no POP readback, no sorter par touched). After it: no warning.
- **Existing PX:** `indep_upgrade(parent_path, name=)`: i_texts (px_logic / px_rt), i_exprs (eff_in), i_hot (own hot
  row follows the stack), done; `_ui_safe`, zkit panel parked, steps UPGC_GAP 20 frames apart, waits on a pending
  recompile; `indep_result()` in a later exec. b2 proof on two loads of library/PX_pointfx (one in sprites mode):
  `changed` px_logic, px_rt, eff_in:chops, presets_kept True, errors 0, warnings 0; second run `changed: []`.
- BL_splat_render's `Splatfx` (it named /project1/lab/PX_pointfx) is now an optional COMP par (empty = off):
  `builders/splat_render.py indep_upgrade`; `px.bl_pointer` delegates to it.
