# px_geo: geometry and lights in the splat scene (W1-E, 27 Oct 2026, TD 2025.31550)

User (27 Oct): "ability to place lights geometry in 3d space and it should effect the splats". Plan row: W1-E in
`RUBENFRO_COVERAGE.md` (GE1 meshes with occlusion both ways, GE3 chrome, GE4 emissive geometry, L1 / L3 lights).

**Status: LIVE-VERIFIED on b3 and brought home to main (27 Oct, TD 2025.31550; JazibTD_home.542, both COMPs parked;
library 0.2.0).** Results: "Verified live" below; live facts T-167. Open: G8 per-splat numbers, env capture cost.

## What it does
Placeable geometry (boxes, planes, spheres, imported SOP / FBX meshes, Text SOP text) renders in the SAME frame as the
splats with correct occlusion both ways, lit by the same Light COMPs:

1. `geo_render` (Render TOP): the user's Geometry COMPs (`Geocomps`), opaque, depth write, lights = `Geolights`
   (Light COMPs; `#light` = every Light COMP in `/project1/effectors`, W1-A kind `light`) + `geo_key` (built-in key
   light, `Geokey`) + `geo_env_light` (`Geoenv`). Any material: MX_prox_material (`apply_prox_material`), PBR, Phong,
   Constant.
2. `geo_pass` (Render Pass TOP, input `geo_render`): draws the splat geo `draw` over geo_render's colour AND depth;
   `splatmat` depth test ON (expression `Geoon`), depth write OFF, premultiplied "over" as always, still back-to-front
   sorted. Behind geometry = rejected by the depth test; in front = blended over it. The pass makes the order explicit
   (geometry first), so nothing depends on draw priority.
3. `geo_switch`: input 0 = `render` (the unchanged BL path), input 1 = `geo_pass`; index = `Geoon`; feeds `post`.

Geo off (default): `geo_switch` passes `render` through, `splatmat.depthtest` evaluates False (as before), the shader
text is exactly the old text, the MAT has no `uGeo` block, and geo_render / geo_pass / geo_env_cube draw nothing
(their geometry expressions are empty while off), so their always-on viewers cost ~nothing. So BL's default output is unchanged (tested offline: same
preprocessed tokens AND same SPIR-V bytes as HEAD a1e49f7; LIVE CHECK G1 confirms the pixels).

Splat relight (L1 on BL): `SPLAT_HOOK_LIGHT` relights each splat's colour (SH0 + SH1 result, after brightness / gamma
/ sRGB) by the light effectors: `rgb = mix(rgb, rgb * (ambient + sum lights), Georelight)`, normal = the splat's
smallest-scale axis facing the eye (W1-A `pxeSplatNormal`), model `Geolightmode` (W1-A `pxeLight` mode.x: half-lambert
/ lambert / wrap / no-normal glow). v1: every enabled light, no specular, no shadows. Default `Georelight 0` = baked
colour. Active only when the effectors block in front of the shader carries W1-A's light functions (`geo_patch` then
defines `SGEO_LIGHTS`); before W1-A lands the hook stays empty even with Geo on.

Depth bias (`Geodepthbias`, default 0): moves each splat's depth (not its position) toward the camera by a world
distance, so a scan floor lying on a placed plane wins the depth test instead of z-fighting.

Chrome / reflective objects (GE3): `Geoenv` builds a low-res cube map of the splats (`geo_env_cube`, `Geoenvres` px)
seen from `Geoenvcentre` (put it at the chrome object) -> `geo_env_equi` (Projection TOP, equirect) -> `geo_env_gate`
(Switch TOP: the 1 px `geo_env_idle` except every `Geoenveveryn` frames, so the cube only cooks then) ->
`geo_env_hold` (Cache TOP, size 1: holds the last map) -> Environment Light COMP `geo_env_light`, added to geo_render's
lights; `geo_env_pull` (Execute DAT) cooks the hold each frame while Geoon + Geoenv (an Environment Light COMP does
not pull its map TOP). The cube render gets `geo_key` as its light. MX preset **Chrome mirror** (metal 1, roughness 0.04-0.06) then
shows the scan. Splats render correctly into the cube at any resolution (the MAT's pixel focal length and NDC offset
both scale with `uRes`, which cancels), but they are sorted for the main camera, so far-off-axis faces of the cube can
show order errors; at 256 px on a glossy object that reads as blur.

Emission / glow (GE4): MX emission (Emitbase, proximity Emission, rim) is HDR in the 16F render, so it blooms wherever
a glow follows: PX's glow pass once PX gets the Geo page (wave 2), or FX chained after BL `out1`. BL itself has no bloom
(not added: no bloat). Colour sources for emission come with W1-B in wave 2.

Meshes as effectors (GE2) stay as they are: a mesh's points as a `pts` set (effectors list) / MX point sets.

## Files
| File | What |
|---|---|
| `builders/splat_render.glsl` | two new hooks, empty by default: `SPLAT_HOOK_CLIP(clip, vc, z)` after the clip position, `SPLAT_HOOK_LIGHT(rgb, p, q, s, idx)` before the colour is written. Called WITHOUT `;` so the defaults add no token |
| `builders/glsl/splat_geo_adapter.glsl` | `uniform vec4 uGeo` (relight, ambient, light model, depth bias); defines the two hooks (macros end with `;`); light part only under `PXE_HOOK && SGEO_LIGHTS` |
| `builders/splat_render_logic.py` | `geo_patch` / `geo_strip` (text in / out, after the effectors block; `SGEO_LIGHTS` when W1-A's functions are there), `geo_has_lights`, `geo_geometry`, `resolve_lights`, `geo_uniform`, `geo_warning` (sort-free), `env_render_now`, `splat_normal`, `geo_relight_ref`, `LIGHTMODES`, `GEO_PARS`; `cpu_reference_raster(base=, depth=, bias=)` = the occlusion reference |
| `builders/splat_render.py` | Geo page (`geo_pars`), `geo_stage` (geo_key, geo_render, geo_pass, geo_switch, MAT depth test), `geo_env` (calls MX's `env_capture`), `geo_sync`; Geo panel page; stage box "3b Geometry" |
| `builders/splat_render_rt.py` | `geo_sync` (text + `uGeo` block follow `Geoon`; par_exec calls it), `geo_lights` (geo_render's lights expression), `_geo_uniform`, `_slot` |
| `builders/prox_mat.py` | `env_capture(c, prefix, geo_expr, centre_exprs, res_expr, everyn_expr, dimmer_expr, make_light)` (camera + cube Render TOP + Environment Light); MX demo `env1` follows `Envmode` |
| `builders/prox_mat_logic.py` | Environment page (demo only: Envmode gradient / top / scene, Envtop, Envgeo, Envcentre, Envres, Enveveryn, Envdimmer); preset `chrome_mirror` |
| `test/test_px_geo.py` | 31 offline tests (below) |

## Geo page (BL_splat_render)
| Par | Default | What |
|---|---|---|
| Geoon | off | geometry in the scene (re-patches the shader text; the rest are expressions) |
| Geocomps | '' | Geometry COMPs: absolute paths / patterns, space or comma separated (`draw` is ignored) |
| Geolights | `#light` | Light COMPs for the geometry: paths, `#tag`, `#light` = all in /project1/effectors |
| Geokey | on | built-in key light `geo_key` (lights the geometry when no light effectors exist) |
| Georelight | 0 | relight the splats by the light effectors (0 = baked colour) |
| Geoambient | 0.25 | ambient for the relight |
| Geolightmode | half-lambert | splat light model (W1-A modes) |
| Geodepthbias | 0 | splat depth toward the camera (world units) |
| Geoenv, Geoenvgeo, Geoenvcentre, Geoenvres, Geoenveveryn, Geoenvdimmer | off, `draw`, 0 0 0, 256, 4, 1 | scene cube for chrome objects |

Use (in TD, after a build): set `Geocomps` to e.g. `/project1/lab/MX_prox_material/geo_sphere` or your own Geometry
COMP (Box / Text SOP / File In SOP / FBX), `Geoon` on. For chrome: `apply_prox_material(<geo>)`, preset Chrome mirror,
`Geoenv` on, `Geoenvcentre` = the object's position. Sort mode must be a sorted one (`geo_warning` puts a note in
Status for sort-free: sort-free adds splats with no order, so it cannot occlude correctly).

## For the wave-2 PX owner (don't edit px*.py here; this is the recipe)
* Pars: `exec(splat_render.py)`, `geo_pars(c, L)` on PX (L = splat_render_logic module; or copy the 14 rows).
* Splats: `sw = geo_stage(c, <PX splat Render TOP>, draw=<splat Geometry COMP>, mat=<splat MAT>, cam_expr=...,
  res_exprs=...)`, then wire `sw` where the Render TOP went; PX's splat DAT text = `geo_patch(text, adapter, Geoon)`
  (it composes with `px_splat_adapter.glsl`: different hooks; tested `PX splat adapter + geo` compiles). PX needs its
  own `geo_lights` / `geo_sync` (copy the ~40 lines of `splat_render_rt.py` or call them with PX's op names; they take
  dat / adapter / mat / logic names).
* Sprites (additive): same pattern: geo_render -> Render Pass TOP drawing the sprite geo with depth test on / write
  off; behind = rejected, in front = added.
* Lights on the splats: PX's `light` colour module (wave 2 item 2) replaces `SPLAT_HOOK_LIGHT` inside PX (do not
  relight twice: leave `Georelight` 0 there or route it to the module).

## Offline tests (`python3 -I -m unittest discover -s test -p 'test_px_geo.py'`, ~3 s, glslc 2026 Homebrew)
* **Identity:** BL vertex + pixel: preprocessed token stream (glslc -E) with the new hooks = without them, for BL alone,
  BL + the effectors block (PXE_POINTS), PX's `px_splat_adapter` and `px_glow_adapter`; SPIR-V bytes equal (BL alone);
  `geo_patch(off)` byte-identical, on -> off round trip byte-identical. Checked once by hand against HEAD a1e49f7's
  `splat_render.glsl`: tokens equal (916 vertex, 131 pixel), SPIR-V equal (21296 / 3320 bytes).
* **Patch:** the effectors marker matches `effectors_logic.MARK_B`; effectors-then-geo = geo-then-effectors + geo_sync;
  idempotent; strip both = original; `SGEO_LIGHTS` only with W1-A's functions; leading `#define` lines stay first.
* **Compile (glslc, OpenGL):** BL + geo; BL + effectors + geo; the light branch (W1-A's real functions from the
  working tree when present, else stubs with their signatures); PX splat adapter + geo.
* **Occlusion reference** (`cpu_reference_raster` base / depth / bias, 64 x 64): no geometry = old image exactly;
  geometry in front = geometry pixels exactly; geometry between = near splat over it, far splat gone; geometry behind a
  dense splat = splat over it (alpha > 0.95); depth bias 0.05 lets a splat 0.02 behind a surface win; equal depth passes.
* **Lights:** `splat_normal` (smallest axis, rotated, batched); agrees with W1-A's `effectors_logic.splat_normal` when it
  exists (sign-free); `geo_relight_ref` (off = baked, normal faces the eye, ambient + light, half mix).
* **Helpers / MX / builder:** `resolve_lights`, `geo_geometry`, `geo_uniform`, `geo_warning`, `env_render_now`;
  Environment page demo-only with default gradient; Chrome mirror preset; builder API + off-path expressions; T-70 /
  T-74 / ASCII on the new functions.
Also green: `test_splat_render.py` (29), `test_prox_mat.py` (35).

## LIVE CHECKS (phase 2; on the TD the main session assigns, scratch first for the new Render Pass path, T-83)
| # | Check | Expected |
|---|---|---|
| G1 | rebuild BL; `geo_notes` in the reply; Render Pass TOP par names (clear depth / clear colour: `cleardepth` / `clearcolor` tried first); td_errors | notes empty, no errors; with Geoon off out1 diff vs a capture taken before the rebuild (Autorbit 0, Frozen sort, same frame) = 0; `splat_glsl` text sha = before |
| G2 | splatmat depth function default | less-or-equal (reference passes equal depth); if `less`, note it (bias covers it) |
| G3 | occlusion: box in front of the splats / a box behind dense splats / a plane through the scan | in front: out1 pixel = geo_render's pixel within 2/255; behind dense splats: box contributes < 5 % (alpha > 0.95 over it); through: the scan cut cleanly at the plane |
| G4 | splat order with Geo on | info inversions <= 0.05 % (BL R2), same as off |
| G5 | Geoon on / off / on | only splat_glsl recompiles; off = exact old text and no `uGeo` block; Status note for sort-free |
| G6 | lights: `#light` with W1-A light effectors; geo_key | geo_render.par.lights = the effectors' Light COMPs (+ geo_key); an MX mesh in Geocomps lit by the same Light COMP as MX's own demo; add / remove a light effector: does geo_render's lights expression update (findChildren dependency)? if not, add a dependency (effectors table) |
| G7 | env capture: Render TOP cube token (`rendermode`), `render` par every N (holds the last cube?), cube res, TDCameraIndex per face | cube renders the splats on all 6 faces; `render` off holds; cost <= 0.6 ms at 256 px every 4 frames (131 k splats); chrome sphere shows the scan |
| G8 | relight (after W1-A lands): one point light at (0, 1, 0), Georelight 1 | probe splats' colour = `geo_relight_ref` with W1-A's `ref_light` within 1e-3 |
| G9 | MX demo: Envmode gradient (default) vs before; scene + Chrome mirror | gradient: M3 diff unchanged (0); scene: sphere reflects torus / plane |
| G10 | Text SOP geo, File In SOP mesh, FBX COMP (children rendered when the FBX COMP is listed?) | all render and occlude |
| G11 | perf, other COMPs parked | Geo off = baseline cook ms; Geo on with 3 objects: + geometry cost only (~0.3-0.5 ms) ; project 60 fps |

## Verified live (27 Oct 2026, TD 2025.31550; b3 = main's BL / MX exported read-only, then main by builder)
Bring-home path: `geo_upgrade()` / `env_upgrade()` (no full rebuild, no effectors re-attach) + `geo_panel()` /
`panel_only()` in their own execs; the same steps ran in main. Captures in `output/px_geo/` (git-ignored).

| # | Result |
|---|---|
| G1 | geo_upgrade on b3 + main: notes empty, td_errors clean (only the old `to_pop` "more channels" warning). Same camera / sort A/B on b3: out1 with the new text + geo_switch path vs the OLD shader body (a1e49f7) wired render -> post: **EXR byte-identical**; Geo on with no geometry: byte-identical too. Main's splat_glsl sha after = b3's (1c71ada8) |
| G2 | Render Pass TOP pars `cleardepth` / `clearcolor` (set off); splatmat `depthfunc` = `lessorequal` |
| G3 | box in front: out1 = geo_render exactly over the box (max diff 0.0); box behind the pinata: where splat alpha > 0.95 the box adds <= 0.051 (expected (1 - a) x box <= 0.047 + 8-bit rounding); a plane through the scan cuts it cleanly (`g3_plane_out.png`), boxes front + back (`g3_both_out.png`) |
| G4 | sort path untouched; Geo on / off identical with no geometry (G1), so same draw order |
| G5 | Geoon off -> exact off text (sha), no geo block, `uGeo` name cleared; on -> block + `uGeo` |
| G6 | `#light` resolves Light COMPs under /project1/effectors; a light added later lit the PBR box with no par touch (render-level check); `#tag`, paths, `geo_key` OK |
| G7 | cube token `cubemap`; **Render TOP `render` off = black (no hold)**, a Cache TOP alone pulls its input every frame, the env light never pulls its map -> gate + hold + pull chain above; with viewers off the cube cooked ~every 4-6 frames; a chrome PBR sphere shows the scan floor (`g7_chrome_preview.jpg`). Cost in main (185 k splats, 256 px, every 4): BL median 16.2 ms / p90 44 ms vs 7.9 ms without env: **far over the 0.6 ms target** (6 splat renders per capture). Use it only when needed; levers: Geoenvres 64-128, Geoenveveryn 8-30, a thinned splat copy |
| G8 | (W1-A committed; b3: effectors rebuilt v2 + BL re-attached, one point light) `SGEO_LIGHTS` compiled; relight 1, ambient 0.5, light intensity 0: out1 = 0.5 x baked within 0.5 / 255 on all 412 706 unclipped opaque px (alpha unchanged); intensity 3: 2.78 x brighter, 99.5 % of px brighter. Per-splat numbers vs `ref_light` (1e-3): not done. **Main's BL still carries the pre-W1-A effectors block**, so relight in main needs `attach('/project1/lab/BL_splat_render')` (left to the W1-A / main session) |
| G9 | MX on b3: Envmode gradient (default) out1 **EXR byte-identical** before / after env_upgrade; scene: the env map shows torus + plane (`g9_env_equi.jpg`) once the cube render got `light1` (without lights MX meshes render black into it); main: env chain cooks in scene mode (env_pull), render_out lights kept (`light1 env1` + W1-A light effectors); a layout back wire env_cube -> env_equi after env_upgrade in main was fixed by hand (positions) |
| G10 | Text SOP, File In SOP (UtahTeapot.obj), FBX COMP (TDLogo.fbx; listing the FBX COMP renders its child Geometry COMP) all render and occlude (`g10_preview.jpg`) |
| G11 | main, out1 force-cooked per frame, other lab COMPs parked, 6 TDs on the GPU (noisy, not paired A/B): Geo off: BL 5.5-7.0 ms median, geo ops 0 cooks; Geo on, 3 objects (2 boxes + a sphere, PBR): 7.9 ms median (~+1-2 ms); + env: 16.2 ms. Real fps 23-45 while sampling (shared GPU) |

## Not in v1
Shadows of geometry on the splats (later in the haze pass, W1-D), splats casting on geometry, per-light selection
for the splat relight (all enabled lights), specular on splats, glow inside BL (use PX / FX after out1).

## In PX (wave 2, 27 Oct 2026; docs/builds/px.md "Wave 2")
PX_pointfx has the Geo page (same par names) + Geoadd. 31550 allows ONE Render Pass TOP per Render TOP (T-178 (2)), so
PX chains geo_render -> geo_pass (splats) -> geo_spass (sprites, pool, glow) -> geo_out; PX relights splats with its
`light` module (uGeo relight stays 0). Live b5: off = diff 0, box in front exact, behind = splat over it (0.007).
