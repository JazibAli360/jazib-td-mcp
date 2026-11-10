# Shared effectors: `/project1/effectors` + adapters (26 Oct 2026, TD 2025.31550)

User asks (26 Oct): "proximity and effectors needs to be in splats nd all" and "i want it modular so if i want i can add
more effectors in it" (`px_requirements.md` items 11 + 12). One list of effectors that the user grows, used by every
COMP that reacts to proximity, with the maths in one place (`builders/glsl/px_common.glsl`, shared with PX + MX).

**Status: LIVE on 31550 (26 Oct ~21:00): built + verified on build TD b2, brought home into the main .toe (`/project1/effectors`
+ the consumer COMPs, parked; main saved JazibTD_home.344.toe; main on 27 Oct has 14 consumers in 9 COMPs: BL_cloud_morph, BL_splat_render, BN_cloth, BN_fluid2d (2), BO_particles, FX_destroy, GEN_clone, MX_prox_material, GEN_points (6 modules), MAIN_AUDIT_27OCT E1). Numbers: "Live results" at the end; facts T-125.**
Offline: 27 tests (`python3 -I -m unittest discover -s test -p
'test_effectors.py'`, ~2 s): list edits, names, selection, tag limit, packed layout = PX's uE rows, point sets, 200
effectors (no cap), weights vs PX's numpy reference, colliders, 2D-sim rows, paths, shader prefix idempotence, builder
API + T-67/T-70/T-74/T-115 text rules, and glslc compiles (TD stubs, not a TD compile) of: particles state (both
modes), splat MAT (both stages), cloud vertex, eff_field2d, PX legacy path, MX stages (test_prox_mat). Affected suites
still pass (prox_mat, particles, px, reaction_diffusion, physarum, fluid2d, cloth, splat_render, pointcloud).
**Lights (27 Oct, W1-A, offline):** kind `light` (section "Lights"): 24 more tests in `test_effectors_lights.py`
(~0.2 s; test_effectors 29 still pass with the v2 layout); not live yet.
**Env light + voxel grid (27 Oct, lane E, offline, packed version 3):** kind `env` (section "Env light (SA6)"): 21 tests
in `test_effectors_env.py`; the shared voxel grid + kind `cloud` + paint volume (section "Voxel grid"): 19 tests in
`test_effectors_grid.py`; not live yet.

## Files
| File | What |
|---|---|
| `builders/effectors.py` | `build()` the COMP; `add / remove / duplicate / rename / enable / set_value`; `attach(comp)` / `attach_all()` adapters |
| `builders/effectors_logic.py` | pure: list table, kinds, tags + selection (`sel_vec`), packing (`pack_buffer`), paths, colliders, 2D-sim values, numpy weight reference, consumer GLSL header / prefix |
| `builders/effectors_rt.py` | TD runtime (Text DAT `eff_rt`): rows cook, objects, list edits, pulses, `select_ops` / `info_2d` for CPU consumers, path expressions |
| `builders/glsl/px_common.glsl` | packed section `#ifdef PXE_ROWS` (`pxeCount`, `pxeSel`, `pxeSd`, `pxeGrad`, `pxeW`, point sets...); legacy uE path kept |
| `builders/glsl/eff_consumer.glsl` | adapter helpers: `pxeParticleForce / pxeKill / pxeSpawnAt` (PXE_PARTICLES), `pxePointFx` (PXE_POINTS) |
| `builders/glsl/eff_field2d.glsl` | compute: the effectors as a 2D field on a world plane (force / dye / mask) |
| `test/test_effectors.py` | offline tests |
| `test/test_effectors_lights.py` | offline tests of kind `light` (layout, references vs closed forms, palette, TD text, glslc) |
| `builders/effectors_grid_logic.py` | pure: grid atlas layout, Grid page, packed grid region, numpy twins of every grid pass (scatter, seed, JFA, query, paint, trilinear) |
| `builders/effectors_grid.py` | TD module (Text DAT `eff_grid`): builds `/project1/effectors/grid`, scatter passes per cloud row (`sync`), parking, paint pulses |
| `builders/glsl/eff_grid_scatter.glsl` / `_seed` / `_jfa` / `_paint` | the grid's compute passes; grid accessors (`pxg*`, `pxePaint`) at the top of `eff_consumer.glsl` |
| `test/test_effectors_grid.py` | offline tests of the grid (layout, K36 field vs brute force, paint, glslc) |
| `test/test_effectors_env.py` | offline tests of kind `env` (v3 layout, SH9 vs closed forms + brute force, maps, selection, TD text, glslc) |

## `/project1/effectors` (never parked: pulses + every consumer read it)
* `eff_list` (Table DAT) = **the list**, one row per effector: `name kind tags enabled falloff radius exponent gain gizmo
  ref mode`. Edit cells directly or use the Effectors page: **Addkind** (sphere / box / plane / capsule / torus / null /
  pts / path / camera / actor / **light**) + Addname + Addtags + Addref + **Add**; **Target** + **Remove / Duplicate / Rename (Newname) /
  Toggle** (enable); **Refto + Setref** (tie Target to a Null, "Tie an effector to a Null" below); **Sync** (objects to the list); **Track** (frame: every frame, needed for velocity, paths, point
  sets; change: static rigs); Status. zkit panel (pulse Opencontrols). First build seeds `sphere1`, `box1` (tag demo).
* Objects (move / rotate / scale them): object kinds = Geometry COMP + unit wire shape (`giz_mat`), SDF = PX unit shape x
  the object's transform; null / path / pts / actor = Geometry COMP with a 0.12 wire box (the gizmo; for point sets it
  is the points' space). Object kinds with `ref` and `camera` use the ref COMP's transform (no own object). `gizmo` 0
  hides the object. path: Path page (shape circle / line / lissajous / figure8 / noise / chop, speed, phase, size,
  centre, CHOP) drives tx/ty/tz by expression.
* Point sets: `pts` ref = a CHOP (samples tx ty tz / x y z / P0..2, or channel groups `<name>x/y/z` like FT_face_track)
  or a SOP; `actor` ref = a COMP (its `out_pts` / `out_points` / first Out CHOP). <= 4096 points each (brute force per
  sample; mode nearest or density). Per-point velocity from the frame difference. **Tracked people / blobs:**
  `ref` = `/project1/lab/FX_track/out_pts` (valid tracker points, tx ty tz, <= Outpts; `fx_track.link_fx()` adds the
  row `track`, tag `track`; in main .738 it exists, OFF; docs/builds/fx_track.md "Outputs"). FX_track must cook.
* `eff_rows` (Script CHOP, Frame par when Track = frame) = **the packed buffer**, `eff_tex` (CHOP to TOP, rgba32f, 1
  row) = the same data as a TOP.

### Packed format (contract: consumers + PX v2)
One vec4 texture buffer (CHOP channels x y z w, one sample per texel):
| Texel | Content |
|---|---|
| 0 | header: count N, row width W = 10, points start, version 3 (2 = lights, 1 before lights) |
| 1 + i*W + 0..2 | inverse world matrix rows (world -> local, affine) |
| +3 | sdf type (PX 0 point, 1 sphere, 2 box, 3 plane, 4 capsule, 5 torus; 6 = point set), local size xyz |
| +4 | world centre xyz (point set: centroid), world scale |
| +5 | world up axis xyz, speed (units/s) |
| +6 | velocity xyz, enabled |
| +7 | falloff shape (PX FALLOFFS index), radius, exponent, gain |
| +8 | tag bits (<= 24 tags, sorted), kind index (KINDS), points start texel, point count |
| +9 | point radius, point mode (0 nearest / 1 density), density full, id = i + 1 |
| L0 = 1 + N*W | light region header: light count K, block stride LW = 7, **env base E, grid base G** (v3; 0 = none; v2 readers read only x / y) |
| L0 + 1 + k*LW | light block k (section "Lights") |
| E | env region header: env count M, block stride EW = 10, 0, 0 (only when an env is on) |
| E + 1 + m*EW | env block m (section "Env light (SA6)") |
| G | grid region (section "Voxel grid"; only while the grid is on) |
| points | 2 texels per point: (xyz, valid) (velocity xyz, speed); start = header z (after every region) |

Texels 0..5 of a row are **exactly PX's uE rows** (tested), so PX's maths ports by swapping `uE[i*6+t]` for
`pxeT(i, t)`. Rows are in table order with disabled ones kept (ids stay stable while a row is toggled).
**No cap:** loops run to the header count (`PXE_MAX` 65536 / `PXE_PTS_MAX` 4096 only bound them, T-35); adding,
removing, renaming or retagging effectors changes data only, never a shader. Cost scales with the count.

**Consumer contract (GLSL):** bind the buffer as `uniform samplerBuffer uEffRows` (Arrays page, type vec4, Array Type
Texture Buffer, CHOP = a Select CHOP of `/project1/effectors/eff_rows`), prepend
`effectors_logic.consumer_prefix(...)` (defines `PX_PACKED_ONLY`, `PXE_ROWS uEffRows`, the uniforms, px_common,
eff_consumer), set the 4 selection vec4s from `consumer_vecs()`:
`uEffSel` (tag mask, all, on, gain), `uEffIds` (4 effector ids), `uEffMix` (combine, radius scale, ragged, ragged
freq), `uEffFall` (override, radius, exponent, shape). Then `pxeW(p, uEffSel, uEffIds, uEffMix, uEffFall, best)`,
`pxeSd / pxeGrad / pxeAxis / pxeVelAt(best, ...)`.
**Selection** (`Effselect` text): `all` / `*` / empty = all enabled; a name = that effector (up to 4 names); `#tag` or
a bare tag word = a tag (groups: "hands", "demo"...). Unknown words are ignored (the CPU twin reports them).

**PX v2 (not touched here; PX v2 is in progress):** adopt the buffer above in place of `uE[48]`: modules' `effectors`
par becomes a selection text resolved by `sel_vec` (per instance: a uEffSel / uEffIds pair in the module header rows
instead of the 8-bit mask), `pxW` -> `pxeW`, `pxESd/pxEGrad/pxECentre/pxEAxis/pxESpeed` -> `pxe*`, `espdN` drive
sources -> per-selection speed; PX's own `effectors/` objects + `px_eff` table become rows of `eff_list` (kinds map
1:1; `chop` -> `pts`). The legacy uE functions in px_common stay (guarded `#ifndef PX_PACKED_ONLY`) until PX v2 and
MX's `objects` mode no longer need them; then delete them in one change.

## Lights (kind `light`, lane W1-A, 27 Oct 2026; LIVE on b4 (31550), results under "Lights LIVE CHECKS")
User (27 Oct): "place lights ... in 3d space and it should effect the splats", "ability to change colors". One list:
a light is a row of `eff_list` (kind `light`, tag `light` added on Add) whose object is a **TD Light COMP** in
/project1/effectors (or `ref` = any existing Light COMP, e.g. MX's `light1`). The same Light COMP lights TD MATs
natively (`light_render`) and is packed for every shader consumer (`pxeLight*`), so MX meshes and splats / points share
one light.

**The Light COMP** (own lights): Effector page `Ltype` point / spot / area / directional (drives TD's `lighttype` by
expression: spot = cone, directional = distant, **area = point for TD-native lighting**: 31550's Light COMP has point /
cone / distant only), `Lareaw` / `Lareah` (rectangle in local XY, x the object's scale; a bar = a small height). Light
page (TD's own): `cr cg cb` colour, `dimmer` intensity, `attenuated` + `attenuationstart / end / exp` (range),
`coneangle` (full angle) / `conedelta` (soft edge outside it) / `coneroll` (both confirmed live b4). It shines along its
local -Z; on creation: attenuated 0..4, cone 45 / 10, at (0, 1.5, 0) pointing down (TD itself starts a Light COMP at
tz 10 and clamps `attenuationstart` to >= 0.001). Gizmo: Geometry COMP `<name>_giz` (Xform parent = the light via
`parentxformsrc` specify + `parentobject`) with a Switch SOP by Ltype: sphere / cone (length 1) / w x h rectangle / rod;
the `gizmo` column hides it. API: `add('light', tags='key', type='spot', colour=(1, 0.2, 0.8), intensity=2,
cone_angle=30)`; `eff_rt.set_light(op, **values)`; Remove / Duplicate / Rename take the gizmo along.

**Light rows are never proximity effectors**: their row texel 6.w (enabled) is packed 0, so pxeW / colliders / spawn
and every **v1 consumer already compiled in main (W = 10, no light code)** read a v2 buffer exactly as before (tested:
other rows' texels identical, weights unchanged, a W = 10 reader still finds the point sets). No consumer needs a
rebuild for lights to exist; only consumers that want light call the new functions.

**Light block** (7 texels; only ENABLED lights, table order; stride read from the region header):
| t | content |
|---|---|
| 0 | colour r g b (palette applied, below), intensity (dimmer) |
| 1 | world position xyz, type (0 point, 1 spot, 2 area, 3 directional) |
| 2 | forward xyz (unit, the shine direction = world -Z), row index i (its tags / name via row i) |
| 3 | attenuation start, end, exponent, on (1 / 0) |
| 4 | cos(cone / 2), cos(cone / 2 + delta), cone roll, 0 |
| 5 | area half-U (world xyz = local x * w / 2), 0 |
| 6 | area half-V (world xyz = local y * h / 2), 0 |

**Maths** (GLSL at the end of px_common's packed section; numpy twins `effectors_logic.ref_light_factor / ref_light /
ref_lights / splat_normal`): L = unit vector point -> light (area: to the nearest point of the rectangle, two-sided;
directional: -forward). Attenuation = TD's form `sin(clamp((end - d) / (end - start), 0, 1) * pi/2) ^ exp` (off = 1;
directional = 1; live b4: a Phong plane lit natively by the same Light COMP matches it within 0.006). Spot =
`smoothstep(outer, inner, angle) ^ roll` (angle = acos(dot(-L, F)); fitted to TD's own cone live: max error 0.027,
linear-in-cos was 0.12). Shading `mode` =
(model, wrap, spec, roughness): 0 half-Lambert `(n.L / 2 + 1/2)^2` (default for scans), 1 Lambert, 2 wrap
`(n.L + w) / (1 + w)`, 3 no normal = glow by distance (plain points); spec = Blinn `spec * (n.h)^(2 / r^4 - 2)` where
n.L > 0. Result = colour x intensity x attenuation x spot x (diffuse + spec). Shadows: none (v1).

**GLSL API** (any consumer with the adapter prefix, or PX / haze with `#define PXE_ROWS <samplerBuffer>` before
px_common): `pxeLightCount()`, `pxeLightBase()` (-1 = no lights / v1 buffer / eff_none), `pxeLT(k, t)` (raw texel),
`pxeLightPos / Dir / Type / Row / Col(k)`, `pxeLightFactor(k, p, out L)`, `pxeLight(k, p, n, v, mode)`,
`pxeLights(p, n, v, sel, ids, mode)` (selection = the usual uEffSel / uEffIds pair: `all` = every enabled light,
`#tag` / names = those lights; sel.z = on), `pxeSplatNormal(q (w,x,y,z), scale, v)` (axis of the smallest scale, faced
to the eye); `...B(b, k, ...)` variants take the base once (loops). `PXE_LIGHT_MAX` 256 bounds loops only.
- **W1-D haze**: per light `pxeLightPos(k)` (project to the screen for shafts), `pxeLightDir(k)`, `pxeLightType(k)`,
  `pxeLightCol(k)` (the in-scatter colour; pass it as `src` of `pxColSrc` for a haze colour source),
  `pxeLightFactor(k, p, L)` (attenuation x cone at each march step), cone cos `pxeLT(k, 4).xy`, area axes
  `pxeLT(k, 5 / 6).xyz`.
- **PX `light` module (wave 2, PX owner)**: `rgb = mix(baked + emission, baked * (ambient + pxeLights(P, n, v, sel,
  ids, mode)), relight)`; splats n = `pxeSplatNormal(rest q, rest scale, v)`; plain points mode 3.
- **W1-E / BL_splat_render**: `SPLAT_HOOK_LIGHT` calls `pxeLights` on SH0 the same way.

**Colours and the shared palette** (W1-B, `docs/builds/palette_convention.md`): the Light COMP keeps its own colour
(TD-native lighting uses it). /project1/effectors gets a **Lights** page: `Palsource` (custom stops `Palstops` "hex
[pos], ..." or any stop / Lospec preset; file / image sources are not offered here), `Palmode`, `Palinterp`, `Palshift`
(drive it with an expression: beat step / bpm cycle / audio; while it is not constant, eff_rows cooks every frame even
at Track = change, T-113), `Palreverse`, and the light colour source `Lightcolsrc` /
`Lightpalpos` / `Lightpalspread` / `Lightkeep` (`colsrc_pars('light')` without `Lightcol`: **solid = each light's own
colour**, the default). Applied when the rows are packed (`eff_rt.light_palette` -> `pack_buffer(light_cs, light_pal)`):
light k (enabled order) gets `colsrc_eval(cs, rgb_k, rgb_k, k, rows, ctl)`, so `index` = light k takes stop k and a
beat step moves every light one stop on; `palette` = all at one position; `keep` mixes back to the own colour.
Consumers read the resolved colour in texel 0 (no palette uniforms needed). Open: in palette modes TD-native lit MATs
still see the Light COMP's own colour (a Render TOP has no per-light colour override); keep `solid` when MX must match.

**TD-native lighting** (MX_prox_material, any PBR / Phong): `effectors.light_render('<Render TOP>', sel='all',
keep=None)` sets its `lights` par to `effectors_logic.lights_expr(sel, keep)` = keep (its current lights, e.g.
'light1 env1') + the selected light effectors' Light COMP paths (`eff_rt.light_paths`; follows list edits through
Listver; a Render TOP set before the list existed is re-set by `build()`'s `refresh_consumers`).

Cost (expected, measure live): +7 texels per enabled light; CPU pack ~0.05 ms per light; per point per light ~10 texel
fetches + 2 pow (target ~0.02 ms / light / 131 k points).

## Env light (SA6 screen-as-light, kind `env`, lane E, 27 Oct 2026; offline, LIVE CHECKS EV1-EV6)
FX7d SA6: "the scan takes the colour spill of whatever the LED wall / visuals show". One row of `eff_list` (kind `env`, tag
`env` added on Add, `ref` = any TOP) = 9 SH coefficients of light from that TOP, packed after the light blocks; any
consumer with the adapter prefix adds `pxeEnvs(n, uEffSel, uEffIds)` (diffuse light at normal n) to its lighting.
Ramamoorthi-Hanrahan 2001: SH9 irradiance is within ~1 % on average for smooth environments; it rings (lobes over /
under) for small bright sources: a lone pixel reads 6.25 % over at its own direction (tested), so small hard sources
belong to `light` rows, broad spill to `env`.

**The env object** (Geometry COMP `<name>`, gizmo = the w x h panel, Effector page): `Envmap` **screen** (default: the
panel IS the screen, its local XY rectangle `Envw` x `Envh` x the object's scale, shining along its local +Z, seen from
`Envprobe` (world point, default (0, 1, 0)); dOmega = dA cos / r^2 per pixel, back side dark unless `Envtwosided`) /
**equirect** (lat-long all around the probe, TD's Projection TOP convention, checked live b2: u 0 = +X, 0.25 = +Z, 0.5 = -X, 0.75 = -Z, v 1 = +Y; the object's rotation turns it) /
**ambient** (the image mean from every direction); `Envgain`; `Envsamples` (fit width, default 32: equirect 32 x 16,
screen 32 x round(32 h / w)). New env objects start at (0, 1.5, -3), facing +Z (the scene). Inside it: `env_src`
(Select TOP = ref) -> `env_fit` (Resolution TOP, `env_fit_size`, rgba32float, input smoothing mipmap = area
average) -> `env_px` (TOP to CHOP, downloadtype nextframe: one frame late, no stall); eff_rows reads env_px
(`eff_rt.env_of`) and projects in numpy (`effectors_logic.env_coeffs`: one 9 x n matmul per cook, the sample basis
cached per geometry). API: `add('env', ref='/project1/lab/FX_x/out1', map='screen', w=8, h=4.5, gain=1.5)`,
`eff_rt.set_env(op, **values)`.

**Env block** (EW = 10 texels; only ENABLED envs with values, table order): 0 (gain, row index i, map 0 screen / 1
equirect / 2 ambient, 0), 1..9 = c_k (rgb, 0), k in `sh_basis` order (Y00, y, z, x, xy, yz, 3z^2 - 1, xz, x^2 - y^2),
pre-convolved with the clamped cosine (x A_l / pi = 1, 2/3, 1/4). A white Lambert surface with unit normal n gets
`gain x max(0, sum_k c_k Y_k(n))`; a uniform white sky of radiance 1 gives 1 (tested 0.5 % at 32 x 16). Env rows are
never proximity effectors (texel 6.w = 0), exactly like lights.

**GLSL** (end of px_common's packed section): `pxeEnvBase()` (-1 = none / before v3), `pxeEnvCount()`,
`pxeEnvIrr(m, n)`, `pxeEnvRow(m)`, `pxeEnvs(n, sel, ids)` (selection like lights: `all`, `#tag`, names), `...B(e, m,
...)` variants; `pxeExtBase(c)` reads the light header's z / w. `PXE_ENV_MAX` 64 bounds loops. Numpy twins
`ref_env / ref_envs`, brute force `env_irradiance_brute`. Consumers: PX `light` module `rgb += baked x pxeEnvs(n, sel,
ids) x Envamount` (W3, PX owner); BL_splat_render's `SPLAT_HOOK_LIGHT` likewise with `pxeSplatNormal`.

Cost (expected, measure live EV5): CPU ~0.05 ms per env per cook (fit download is a TD op on nextframe); GPU 10
texel fetches + ~30 ALU per point per env (~0.01-0.02 ms per env per 131 k points).

### Env LIVE CHECKS (any free TD; scratch first for the shader one)
| # | Check | Expected |
|---|---|---|
| EV1 | `add('env', ref=<Ramp TOP>)`; env_fit / env_px | Resolution TOP is 32 x 18 rgba32f; a 1-pixel white dot in a black 1920 x 1080 TOP: sum of env_fit pixels x (32 x 18) / (1920 x 1080) = 1 +-5 % (mipmap = area average; if not, set the right smoothing par + LEARNINGS); env_px channel names r0 g0 b0 a0 r1 ... (T-87) and row 0 = image bottom (else flip in `env_pixels_from_chop`) |
| EV2 | env_px downloadtype + cooks | `nextframe` accepted; with a moving Noise TOP as ref, eff_rows cooks every frame at Track = change too (it reads env_px); a static ref: no cooks |
| EV3 | packed numbers | header version 3, light header z = env base; `read_env` block = `env_coeffs` of the same pixels (env_px numpyArray fed to the logic offline) within 1e-6 |
| EV4 | GPU vs numpy (scratch, a disposable compute with the adapter prefix): pxeEnvs over 64 x 64 normals for a screen env and an equirect env | = `ref_envs` within 1e-4 |
| EV5 | look + cost: BL_splat_render / PX (when its light module reads envs) with a red-to-blue Ramp as the wall | the scan takes the wall's colour on the side facing it; eff_rows CPU + consumer GPU per env (target ~0.05 ms CPU, < 0.02 ms GPU per 131 k points); real fps 60 |
| EV6 | equirect convention | an equirect from TD's Projection TOP (cube -> equirect) of a scene with a red light on -Z: the red lobe lands on normals facing -Z (else adjust `env_samples` equirect mapping only + LEARNINGS) |

## Voxel grid (shared service, lane E, 27 Oct 2026; offline, LIVE CHECKS VG1-VG8)
Build plan 27 Oct s2: ONE coarse voxel grid in /project1/effectors, built with its first two real users: the K36 / GE2
distance field (proximity from point sets > 4096 points and dense mesh samples) and the SA23 painted mask volume. SA5
bounce / SA3 opacity shadows / SA21 heat spread / SA14 density read it later (PX W3). 2D-tiled atlas in rgba32f compute
TOPs (T-47 class), no Texture3D, no POP buffers (T-124), no image atomics (shared-memory atomics only).
**Off by default and cheap:** `/project1/effectors/grid` is parked (allowCooking False) unless `Gridon` or `Painton`
is on (Parameter Execute `grid_pars` -> `eff_grid.park`), and its TOPs cook only when a consumer pulls them; a static
cloud TOP does not recook the chain.

**Layout:** a cube (Grid page `Gridcentre`, `Gridsize` = edge) of N^3 voxels (`Gridres` 16 / 32 default / 64 / 128;
paint `Paintres` 32 / 64 default / 96 / 128; N multiple of 8). Voxel (x, y, z) = atlas texel (x + (z % TX) N, y + (z //
TX) N), TX = ceil(sqrt N): 32 -> 192 x 192, 64 -> 512 x 512, 128 -> 1536 x 1408. Centre of a voxel = origin + (v + 0.5)
cell. Packed (v3): the light header's w = G; texel G = (layer count, 2, 0, 0), per layer (origin xyz, cell), (N, TX,
kind 1 field / 2 paint, on); consumers find a layer with `pxgLayer(kind)`, so the uniforms come with the buffer.

**Kind `cloud`** (K36 / GE2): a row whose `ref` is any TOP of points (rgb = xyz in the cloud object's space, alpha >
`Gridalpha` (0.5; -1 = all) = valid; e.g. BO_particles' state, PX's rest texture, a pointcloud / Sprinkle SOP to TOP);
its object (Geometry COMP, small box gizmo, `cloud_src` Select TOP inside) moves the points. Packed: sdf type 7, texel
3.y = on, texel 6.w = 0, so v1 / v2 consumers (and every consumer compiled without `PXE_GRID`) never see it; with
`PXE_GRID` it joins `pxeSel / pxeSd / pxeGrad / pxeW` like a point set (row radius = point radius, falloff, tags), any
point count. CPU twin: `effectors_logic.ref_weight(..., field=(vol, geometry))`.

**Field passes** (`grid`): per enabled cloud row (table order) `src_<name>` (Select TOP of its cloud_src) ->
`scat_<name>` (input 0 = the previous pass / `none`): one workgroup per 8^3 brick (dispatch N/8 cubed, 512 threads),
each walks every point and adds those in its brick with shared uint atomics: (sum of cell-local offsets xyz x 1024,
count) -> `seed` (centroid world xyz, has) -> `jfa1..8` (3D jump flooding, 27 taps, steps N/2..1, +1 extra, then copies;
`jfa_steps`) -> `grid_field` (Null; nearest seed per voxel). Query `pxgFieldNearest(p)` = min |p - seed| over the 8
voxels around p: **error vs brute force < 1 cell** (tested: 20 000-point sphere, sparse, clustered sets; median <
0.3 cell). Scatter cost grows with points x bricks (each brick reads every point): 65 k points at 32^3 = 64 bricks x
65 k reads; 128^3 is meant for static clouds.

**Paint (SA23)**: `paint_init` (Switch: black / `paint_file`) -> `paint_fb` (Feedback) -> `paint_step` -> `paint_out`.
Per voxel centre: `paint' = clamp(paint (1 - Paintdecay dt) + Paintrate dt (wPaint - wErase), 0, 1)`, w = `pxeW` of the
`Paintselect` (default `#paint`) / `Eraseselect` (`#erase`) selections, each effector's own falloff (any kind: a hand
point set paints). Out (paint, wPaint, wErase, 1). `Paintclear` (feedback reset held 3 frames, T-85), `Paintsave`
(writes `paint_out` to `Paintfile`, default `paint/effectors_paint.exr` in the project folder; a user pulse, never per
frame), `Paintload` (reads it back as the start state). Consumers: `pxePaint(p)` (trilinear r).

**Consumer contract:** define the samplers BEFORE the adapter prefix (`effectors_grid_logic.consumer_defines(field,
paint)`): a GLSL MAT adds Samplers-page samplers `sEffGrid` = `/project1/effectors/grid/grid_field`, `sEffPaint` =
`.../grid/paint_out` + `uniform sampler2D sEffGrid;` and `#define PXE_GRID sEffGrid`; a GLSL TOP uses a free input
(`#define PXE_GRID sTD2DInputs[k]`; a GLSL TOP has 3 inputs, T-123). The accessors (`pxgLayer`, `pxgFetch`,
`pxgSample`, `pxgFieldNearest`, `pxgFieldSd`, `pxePaint`) live at the top of `eff_consumer.glsl` (the adapter prefix
appends it); px_common carries only `PXE_SD_GRID` + the three `#ifdef PXE_GRID` hooks. Consumers without the defines
compile exactly as before (tested). No consumer is wired to the grid yet: PX W3 (SA5 / SA21 / SA23 masks) and the
adapters take it when their owners add it.

### Grid LIVE CHECKS (scratch first: a new compute class, 3D local size + shared atomics; no POP, so the other TDs need not idle)
| # | Check | Expected |
|---|---|---|
| VG1 | `build()` twice | grid COMP made, parked (Gridon / Painton off); 0 errors; `grid_pars` toggles allowCooking; packed header unchanged while off (light header w = 0) |
| VG2 | scatter compiles + dispatch: Gridon, `add('cloud', ref=<Noise TOP 64 x 64 rgb in -1..1, alpha 1>)` | `scat_cloud1` compiles with local size 8 x 8 x 8 and dispatch N/8 cubed (if TD refuses a 3D local size: 512 x 1 x 1 + brick from gl_WorkGroupID, logic unchanged); atlas 192 x 192 rgba32f |
| VG3 | counts = numpy: read scat_cloud1 (numpyArray, one read on scratch) vs `scatter_ref` of the same Noise pixels (numpyArray of the source) | count channel equal for points away from voxel faces (float32 floor at faces may move a point: report the count, expect 0-2 of 4096) ; sum = valid points |
| VG4 | field: grid_field vs `field_ref` | distances |p_voxel - seed| equal within 1e-5 (seed identity may differ at ties) ; `query_ref` vs a disposable compute calling pxgFieldNearest over 4096 random points: 1e-5 |
| VG5 | K36 end to end: BO_particles (or a test compute) compiled with `#define PXE_GRID sTD2DInputs[2]`, Effselect the cloud | particles push away from a 20 k-point cloud body; weights = `ref_weight(field=...)` within 1e-4 at 1000 probe points |
| VG6 | cost (others parked): 65 536 points at N 32 / 64, moving (Noise TOP time-varying) | scatter + seed + 8 JFA GPU ms at 32^3 (expect < 0.5 ms) and 64^3; static cloud: 0 cooks; real fps 60 |
| VG7 | paint: Painton, a `null` tagged paint moved through the grid by a path, then away | painted voxels stay 1 (decay 0); `#erase` effector clears; Paintdecay 0.5 fades; Paintclear -> 0 within 3 frames |
| VG8 | paint save / load | Paintsave writes the EXR (32-bit float); Paintclear; Paintload restores it (max diff 1e-6) |

**Main (27 Oct ~03:24, by builder, quiet minute, lane registered):** `effectors.build(panel=False)` on main's
/project1/effectors: eff_grid / eff_grid_logic / grid_pars + the grid COMP (21 ops, parked), Grid page; header (4, 10,
42, 3) = every consumer's eff_in reads the same 42-sample buffer (only the version number changed); 0 errors under
/project1/effectors; eff_rows 0.55-0.8 ms CPU per frame (path1 makes it cook every frame, as before). No env / cloud /
paint rows added in main (the user adds them). Saved JazibTD_home.606.toe; library/Effectors 0.3.0.

### Env + grid live results (27 Oct 2026, TD 2025.31550, build TD b2; main's /project1/effectors loaded from a read-only save, rebuilt by builder; test consumers in /project1/laneE)
| # | Result |
|---|---|
| VG1 | build x2: grid COMP made, parked while Gridon / Painton off, 0 errors; `grid_pars` wakes it the next frame; header v3 (light header w = grid base only while on) |
| VG2 | scatter compiles with local size 8 x 8 x 8 and dispatch N/8 cubed (accepted); atlas 64 x 64 at N 16 |
| VG3 | 4096 points (64 x 64 GLSL TOP): GPU counts = `scatter_ref(f32=True)` exactly (0 diff), offset sums exact; float64 ref moved 9 points sitting exactly on voxel faces -> `scatter_ref(..., f32=True)` (fix) |
| VG4 | seed vs `seeds_ref` 1.2e-7; JFA = numpy JFA of the GPU seeds exactly (distance diff 0, seed identity 100 %); GPU `pxgFieldNearest` over 4096 points = `query_ref` 2.0e-7; vs brute force max 0.46 cell |
| VG5 | test compute with `#define PXE_GRID sTD2DInputs[1]` + adapter prefix, cloud row #body radius 0.5 linear: weights = `ref_weight(field=...)` max 1.5e-7 (766 / 4096 points weighted) |
| VG6 | 65 536 moving points: per-op `gpuCookTime` stale / noisy under 5 busy TDs (T-169): scatter 0.1-3.6 ms, seed < 0.1, JFA total 0.4-0.9 ms at N 32 / 64, CPU ~0.8-1.2 ms for the chain; needs a quiet-machine measure before relying on 64^3 for moving clouds |
| VG7 | path effector tagged paint (radius 0.3 step) sweeping x +-1.2: trail voxels (r < 0.25) all 1.0, outside 0, stays after the brush leaves; #erase null at the centre clears r < 0.28 to 0, rest stays; Paintdecay 0.5 -> 0.33 after ~2 s (e^-1 expected 0.37) ; Paintclear -> 0 |
| VG8 | Paintsave wrote paint/laneE_test.exr (4155 B); clear; Paintload -> identical to before save (max diff 0) |
| EV1 | env_fit 32 x 18 rgba32f, `inputfiltertype` mipmap = area average: a 1-px dot in 1920 x 1080 keeps 0.982 of its energy; row 0 = image bottom. **Fixed:** TOP to CHOP `crop` default is `row` (one row only) -> `crop full`, `outputcolorspace passthrough`; channels r0 g0 b0 a0 r1 ... (18 rows x 4); Grid SOP has no `sizez` (env object creation failed) |
| EV2 | Track change: static ref 0 eff_rows cooks / 194 frames; moving ref 159 / 195 |
| EV3 | packed env block = `env_coeffs` of the env_px pixels within 8e-16 (version 3, light header z = env base) |
| EV4 | GPU `pxeEnvs` over 64 x 64 normals (screen env + equirect env) = `ref_envs` max 2.3e-7 |
| EV5 | CPU per env per cook: `env_of` 0.145 ms (after the cached name map; was 0.39) + `env_coeffs` 0.09 ms; no consumer reads envs yet (PX `light` W3 / BL hook), so no look capture |
| EV6 | TD Projection TOP (cubemap -> equirect) of red -Z / green +X / blue +Y spheres: u 0 = +X, 0.25 = +Z, 0.5 = -X, 0.75 = -Z, v top = +Y. **Fixed** `env_samples` (was u 0.5 = -Z); after the fix the brightest red / green / blue normals are -Z / +X / +Y. The basis cache key now includes the logic's identity (a hot-reloaded eff_logic reused an old basis) |

## Adapters (thin: an Effectors page + a few ops; `attach()` runs at the end of each builder's `build()`)
Every shader adapter adds `eff_none` (Constant CHOP: empty list when /project1/effectors is missing) + `eff_in` (Select
CHOP of eff_rows) and the page **Effectors**: Effon (default off = the COMP looks exactly as before), Effselect,
Effgain, Effcombine, Effradscale, Effragged / freq, Effoverride + Effradius / Effexp / Effshape (consumer falloff
instead of each effector's). The shader block sits between `// >>> effectors adapter` markers (re-attach replaces it).
Build order does not matter (T-159): `eff_in.chops` and the uEffSel / uEffIds expressions read Effselect before their
"list exists" guard, and `build()` re-sets every consumer's effector expressions (`refresh_consumers()`, count in the
reply as `refreshed`), so a consumer built before /project1/effectors resolves when the list appears.
| COMP | Hook | What effectors do |
|---|---|---|
| BO_particles | `state` compute (both state DATs, `PXE_PARTICLES`) + uEffP / uEffP2 | push (outward), attract, vortex (up axis), wake (effector / nearest point velocity), drag, kill at weight, spawn a fraction at effectors (point sets: at their points) |
| BL_splat_render | `splat_glsl` (`PXE_POINTS`) on `splatmat` + uEffFx / uEffFx2 | per splat: push (outward / axis / velocity), dissolve near or reveal near (dust = per-splat threshold), scale (covariance x factor): splats stay real splats |
| BL_cloud_morph | `pc_vertex` (`PXE_POINTS`) on `pcmat` | the same per point: push, dissolve / reveal, size |
| BN_fluid2d | `eff_force` (force_sel -> force_prep) + `eff_dye` (src_sel -> src_prep), `eff_field_compute`, switches `eff_force_sw` / `eff_dye_sw` (Effon) | force = push / swirl / wake on a world plane (Effcentre, Effplanew / h, default 1.125 x 2), dye = colour x amount x weight; wired in1 / in3 still add |
| BN_cloth | `eff_colliders` (Script CHOP: in3 + selected effectors as spheres) -> engine input 1; Effpad | colliders (sphere r = 0.5 scale, box = half diagonal, null = row radius, point set = a sphere per point; planes skipped; cloth's own NSPHERES cap applies). **Grab: not built** (needs a substep hook) |
| FX_destroy | `eff_mask` (540x960 weight mask of the frame -0.5..0.5, Effplanew / h = 1) | set a module's Masksource `top` + Masktop `eff_mask` (sibling name: a module's OP par resolves beside it, T-125; burn / melt start near effectors); its Point page `Effector` can be any `/project1/effectors` object (tx ty). `builders/fx_destroy.py` belongs to another lane: no hook line there yet (run `attach` after its build) |
| GN_reaction_diffusion, GN_physarum | native: their `Effectors` par also takes `@all`, `@<name>`, `@#<tag>` (engine `_eff_ops` -> `eff_rt.select_ops`) | shared objects inject / steer like their own Nulls; radius = shape half size + row radius, falloff mapped (smooth/gaussian gauss, linear, step/core hard, shell ring), enabled, gain x their Effstrength (`effector_row` gain, tested) |
| MX_prox_material | native: Effectors page `Effsource` (list = default / objects = the v1 uE path, max 8), `Effselect`, `Listfalloff` (effector / material) | `mxProx` reads the list (`pxeW`) in list mode; `apply_prox_material(geo, effectors=[...])` with explicit objects keeps `objects` |
| GEN_clone | native: `builders/gen_clone.py` puts the Effectors page, `eff_in` / `eff_none`, `uEffRows` and the consumer prefix on the `clones` compute pass (`attach` reports it) | weight `pxeConsumerW` at each clone position drives Effoff / Effpush / Effrot / Effscale / Effcolour / Efftime / Effhide (docs/builds/gen_clone.md) |

## LIVE CHECKS (scratch TD first for the shader ones, then main; park when done)
| # | COMP | Check | Expected |
|---|---|---|---|
| E1 | effectors | `build()` twice | no errors; eff_list kept (seeds once); sphere1 / box1 objects; eff_rows samples = 1 + 2 x 10; eff_tex 21 x 1 rgba32f; zkit panel |
| E2 | effectors | Add each kind (Addkind + Add), Duplicate, Rename, Toggle, Remove | rows + objects follow; Remove = safe_destroy; header count follows; no shader anywhere recompiles (consumers' cook time no spike) |
| E3 | effectors | Script CHOP setup | `Frame` par exists; Track frame: eff_rows cooks every frame; change: 0 cooks static, 1 per object move |
| E4 | effectors | path effector (circle, speed 0.25) | tx/ty/tz follow the path (expression dependency on absTime through the module call); row speed ~ 2 pi r x 0.25 |
| E5 | effectors | pts ref = FT_face_track out_pts (or a Noise CHOP 64 samples tx ty tz) | point count / start in row 8; centroid in row 4; velocity texels move with the points |
| E6 | effectors | camera ref = a Camera COMP; object kind with ref | row transform = the ref's |
| E7 | effectors | Constant CHOP `name0/value0` pars, CHOP to TOP `dataformat` / `format` pars, Select CHOP `chops` expression | accepted on 31550 (else fix the par names) |
| E8 | effectors | 100 nulls (`add('null')` x 98) | eff_rows cook ms (CPU) at Track frame; consumers still compile once |
| P1 | BO_particles | rebuild (hook) with Effon off | state compiles; diff vs before = 0 (V1 reference still within 1e-5) |
| P2 | BO_particles | Effon, push 2, sphere1 at origin | particles leave the sphere; kill 0.9 empties it; spawn 0.3 births at sphere1; `tops`-free (buffer via Arrays page, texturebuffer) |
| P3 | BO_particles | perf 65k / 262k with 2 effectors and with a 468-point set | state ms (point set = brute force per particle: report; field path is the next step if > 1 ms) |
| S1 | BL_splat_render | rebuild with Effon off on a .ply / .spz | render identical (diff 0) |
| S2 | BL_splat_render | Effon, dissolve 1 dust on, sphere1 crossing the scan; push 0.3; grow 2 | splats near it vanish per splat (no dots), push outward, grow near; still depth-sorted |
| C1 | BL_cloud_morph | Effon off identical; on: push / reveal (dissolve -1) | points react near effectors only |
| F1 | BN_fluid2d | Effon, move sphere1 across the plane (Effplaneh 2) | dye injected along its path, force pushes / wake drags; Effon off = switches select the old path (no cost) |
| F2 | BN_fluid2d | perf | eff_force + eff_dye compute ms at sim / dye res (expect ~0.2-0.5 each, T-100) |
| K1 | BN_cloth | Effon, sphere1 under the cloth | cloth drapes over it; in3 colliders still add; engine input 1 = eff_colliders |
| R1 | GN_reaction_diffusion | Effectors `eff* @demo` | sphere1 / box1 inject like eff1; gain 0 = no inject; toggled off = gone |
| H1 | GN_physarum | Effectors `@sphere1` | agents steer to it (strength x gain) |
| D1 | FX_destroy | attach; burn1 Masksource top, Masktop ../eff_mask | burn starts near sphere1 (frame -0.5..0.5); eff_mask weight image correct |
| X1 | MX_prox_material | rebuild: Effsource list (default) | demo meshes react to /project1/effectors (sphere1 / box1); `objects` = the v1 look (M3 / M5 numbers unchanged) |
| X2 | MX_prox_material | Listfalloff material vs effector; Effselect `#demo` / `box1` | weights follow the selection; no recompile |

### Lights LIVE CHECKS (W1-A; on the TD the main session names, T-144; scratch first for the shader check)
| # | Check | Expected |
|---|---|---|
| E9 | `build()` (Addkind lists light, Lights page), Add each light type, Duplicate, Rename, Toggle, Remove, hand edit of a light row | rows + Light COMP + `<name>_giz` follow (gizmo follows the light; spot cone opens AWAY from the light, else swap rad1 / rad2 in `_light_giz`); header version 2, light count = enabled lights; no consumer shader text changes, no cook spike; Status "N lights on" |
| L-a | light API in a disposable compute (scratch): point light (0, 1, 0), intensity 2, attenuation 0..3 exp 1, +y plane of 33 x 33 points | `pxeLight` = `ref_light` within 1e-5 for models 0..3 |
| L-b | spot 60 / 10 pointing down on the same plane, GPU vs ref; then a Phong plane lit natively by the same Light COMP (`light_render`) | GPU = ref (1e-5); TD's own pool full inside 30 deg, dark beyond 40 deg; if TD differs (half angle, delta inside), fix `light_block` only + LEARNINGS |
| L-c | MX_prox_material: `light_render(render_out)` (keeps 'light1 env1'); add / disable / remove a light | meshes lit by the effector light; a disabled / removed light leaves `lights` with no error; falloff on a plane has the `sin` shape of `ref_light_factor` |
| L-d | Track change: move the light; change colour / dimmer / cone / Ltype / Palshift | eff_rows cooks once per change, block follows; Track frame: every frame |
| L-e | `Lightcolsrc` index on 3 lights with `neon_trio` steps, then `Palshift` 1/3 (and a beat expression) | packed colours stops 0, 1, 2 -> 1, 2, 0; Light COMP colours unchanged |
| L-f | cost: 8 lights, eff_rows CPU at Track frame; a loop of 8 lights over 131 k points | ~ +0.05 ms / light CPU; ~0.02 ms / light / 131 k GPU; real fps 60 |

**Lights live results (27 Oct 2026, TD 2025.31550, build TD b4; main's /project1/effectors + MX_prox_material loaded
from read-only saves):**
| # | Result |
|---|---|
| E9 | build: Addkind lists light, Lights page, refreshed 14; add point / spot / area / directional: Light COMPs with lighttype point / cone / point / distant, gizmo Switch input 0..3, gizmo world matrix = the light's (parentobject); duplicate (light5, +0.25 x, own gizmo), rename -> beam (gizmo renamed + re-parented), toggle, remove (light + gizmo gone), hand-added row + Sync (object + gizmo made); header (9, 10, 120, 2), light header (4, 7), rows of the lights 4 5 6 8; MX shader text hashes unchanged (no recompile), 0 op errors. Fixed live: Switch SOP index par is `input`; spot gizmo rad1 sits at +z (wide end now rad2); new Light COMP starts at tz 10 (set 0) |
| L-a | GPU compute harness (33 x 33 +y plane, TD-compiled light API): point light intensity 2 range 3: GPU vs `ref_lights` max diff 3.3e-7 / 3.7e-7 / 2.9e-7 / 4.2e-7 (models 0..3); area 3 x 0.5 (ry 30) 3.2e-7; directional 0 |
| L-b | spot 60 / 10: GPU vs ref 7.7e-7 (after the smoothstep change); TD-native Phong plane via `light_render`: full to 30 deg, 0 by 40 deg (coneangle = full angle, delta outside); edge shape = smoothstep in angle (max err 0.027) |
| L-c | TD-native attenuation (Phong, point 2 / 0..3) vs `ref_light`: max 0.006 over 257 x 257. MX_prox_material `light_render(render_out)` kept light1 env1: red light -> render mean r 0.2949 -> 0.3346 (g, b unchanged); disable -> 0.2949 and `la` leaves the lights list; re-enable -> 0.3346; remove -> lights 'light1 env1', 0 errors. Fixed live: `lights` evals to a LIST of OPs (keep now joins their paths) |
| L-d | Track change, static (path removed): 2 cooks / 60 frames (the path effector alone cooks every frame); each of tx / cr / dimmer / coneangle / Ltype / Lightcolsrc / Palshift edit: block follows (cos 0.866 -> 0.906, type 1 -> 2, colours) |
| L-e | neon_trio steps, index: lights = stops 0 1 2; Palshift 1/3 -> 1 2 0; a beat expression steps them over time (Track frame, and Track change after the clock fix); Light COMP colours untouched |
| L-f | 8 lights x 131 044 points (compute, half-Lambert + spec): GPU 0.07-0.18 ms (~0.015 ms / light); eff_rows CPU 1.0-2.6 ms at 13 rows (noisy; light_of 0.06 ms per enabled light, disabled lights no longer read); real fps 59.2 with the harness running |
| main | `effectors.build()` on main /project1/effectors by builder (refreshed 98 consumer expressions, 0 errors; header (4, 10, 42, 2): every parked consumer's eff_in reads the 42-sample v2 buffer unchanged); MX_prox_material `render_out` lights = `light1 env1` + light effectors (`light_render`, keep kept as bare names so the COMP still loads elsewhere); main saved JazibTD_home.534; library/Effectors 0.2.0 re-exported. No light rows added in main (the user adds them) |

## Live results (26 Oct 2026, TD 2025.31550, build TD b2 -> main; T-125)
Consumers were loaded from main's own checkpoints (no edits lost) or, for BL_splat_render / BL_cloud_morph, rebuilt by
their builders in b2 with main's par values re-applied. Shader adapters whose body has `PXE_HOOK` calls (BO_particles,
BL_splat_render, BL_cloud_morph) need the builder's `build()`; `attach()` alone only refreshes the prefix (T-125 (9)).
| # | Result |
|---|---|
| E1 | build x2 clean; 2 seeds; eff_rows 21 samples, header (2, 10, 21, 1); eff_tex 21 x 1 rgba32f (E7 par names OK) |
| E2 | pulses Add capsule / plane / path, Remove plane1, Duplicate (+0.25 x), Rename, Toggle (texel 6.w = 0, id kept): rows + objects + header follow; then +12 mixed kinds = 17; +83 nulls = 100 |
| E3 | Track change: 0 cooks / 60 static frames, exactly 1 per move; Track frame: every real frame (after fixes T-125 (2)) |
| E4 | path circle speed 0.25, r 1: row speed 1.5706 (2 pi r 0.25 = 1.5708), centre = tx |
| E5 | pts = Noise CHOP 64 x tx ty tz: row 8 = (6, 6, start, 64), centroid = CHOP mean, point 0 exact, point velocities ~0.031 u/s when pulled |
| E6 | camera ref + object kind with ref: rows carry the ref's transform, no own object |
| E8 | eff_rows CPU per frame: 4 effectors ~0 when nothing pulls it; 17 = 0.83 ms; 100 nulls = 2.76 ms; 105 + 532 points = 2.65 ms (1.94 without the sets) |
| edits | 5 list edits (add / remove / toggle / hand cell edit) under a running consumer: shader text unchanged, 0 frames > 1 ms (Listver, T-125 (3)) |
| P1 | BO_particles Effon off: V1 reference P 1.2e-6, V 1.1e-6, age 1.8e-6 |
| P2 | push 2 at a dense point: particles within 0.25 of sphere1 1166 -> 57; kill 0.5: alive within 0.5 2628 -> 0 (respawned elsewhere) |
| P3 | 65 536 particles, state GPU: off 0.12 ms, 2 named effectors 0.43-0.56, a 468-point set 0.97, all 105 rows 1.43 |
| S1 / S2 | BL_splat_render 109 529 splats: Effon off vs pre-adapter shader max diff 0; dissolve centre alpha 0.96 -> 0.11 (whole splats, no dots), push 0.96 -> 0.46 (total alpha kept), grow 0.57 -> 0.82; render GPU off 1.68 / named 1.68 / all 105 incl. 532 points 21.4 ms |
| C1 | BL_cloud_morph 49 106 points: off diff 0; push empties the centre (0.091 -> 0); reveal keeps near points (0.0907 kept), drops far; render 1.04 off / 0.92 on |
| F1 / F2 | BN_fluid2d: sphere1 sweeping: dye mean 0 -> 0.18; switches 0 -> 1; eff_force 0.045 ms GPU (192 x 342), eff_dye 0.40 ms (810 x 1440), CPU 0.46 |
| K1 | BN_cloth: collider (0, 0, 0, r 0.52); closest cloth point 0.328 -> 0.530, bottom edge y 0.047 -> 0.315 (drapes); no NaN; colliders 1.4 ms at a 105-row list |
| D1 | FX_destroy: eff_mask compiles (no-input guard), weight centred, 0.073 ms GPU; burn1 Masksource top + Masktop `eff_mask`: mask_src = eff_mask (diff 0); Point Effector takes `/project1/effectors/sphere1` |
| R1 / H1 | GN_reaction_diffusion `eff* @demo` adds sphere1 + box1 (radius 0.5 + 0.5), gain 0 -> 0, disabled -> gone, `@#hands` by tag; GN_physarum `@sphere1` row uv (0.5, 0.5) r 0.5 strength 10, gain 0.5 -> 5 |
| X1 / X2 | MX_prox_material Effsource list (default): renders vs no selection: all 0.286, #demo 0.091, box1 0.059 (#demo vs box1 0.035), Listfalloff material 0.064; MAT text unchanged (no recompile); `objects` = v1 path |
| main | all 10 brought home with ops equal and 0 errors; re-check in main: every adapter's eff_in reads the shared 4-row list (41 samples); RD / physarum native; only note: splat_render to_pop "more channels than attributes" (builder's own) |
Main list after the lane: sphere1, box1 (`demo`), capsule1, path1 (`hands`). MX now follows the shared list by default
(its own eff_box / eff_sphere / eff_null stay for Effsource `objects`).


## 28 Oct: live dropdowns (T-233)
- `Target` (Remove / Duplicate / Rename / Toggle use it) is a StrMenu of the `eff_list` names, labelled
  `sphere1 (sphere)`, with `, off` for disabled rows.
- `Paintselect` / `Eraseselect` and every consumer's `Effselect` get helper items: `all`, `+ name`, `+ #tag`,
  `- word`, `(clear)`. Each item is the whole new text, and you can still type in the field.
- The items come from `eff_rt.menu(comp, name, kind)`. Consumers use `menu_logic.shared_source`, which shows an empty
  menu while /project1/effectors is missing (never an error).
- Name fields on other COMPs (`effectors.MENU_TARGETS`):
  - GN_physarum / GN_reaction_diffusion `Effectors`: own Nulls, `eff*`, `@all`, `@name`, `@#tag`.
  - MX_prox_material `Effectors`: object COMPs here + in the parent. `Envgeo`: its Geometry COMPs.
  - GEN_interactive `Nulls`.
- Builders mark new pars with `'menu': kind`. COMPs built earlier convert with
  `dropdowns_upgrade()` (in place: values, expressions and page order kept; PX has its own `px.oct28_upgrade`).
- On b3: 15 consumers converted. Target follows add / remove at once.

## Tie an effector to a Null (28 Oct 2026; user: how do I tie an effector to a Null?)
An effector of kind sphere / box / plane / capsule / torus / **null** / camera / light can follow any object COMP of
the rig: its `ref` is that COMP's path and the effector takes its world transform every frame (Track = frame; a
`change` list re-reads it when the COMP moves). A light ties to a Light COMP only. Point sets (`pts`, `actor`),
`env` and `cloud` keep their own ref meaning (a CHOP / SOP / TOP), typed in the field or in `eff_list`.
- **Existing effector:** pick it in **Target**, pick the object in **Refto** (dropdown: `(none)` + every Null /
  Geometry / Light COMP under /project1 by path, the effectors' own objects and gizmos left out; the Target's current
  ref is marked `= Target now`), pulse **Setref**. `(none)` + Setref unties it (its own object comes back). Tied, its
  own object is hidden (the next Sync removes it).
- **New effector born tied:** pick the object in **Addref**, then Addkind / Addname / Addtags + **Add** (Addref stays
  set for the next Add, like Addtags; pick `(none)` to stop).
- From Python: `effectors.set_ref('sphere1', '/project1/rig/hand_l')`, `effectors.add('null', ref='/project1/rig/hand_r')`.
- Checks (`eff_rt.check_ref`): the op exists, is an object COMP, is not inside /project1/effectors; a light needs a
  Light COMP. A failure goes to Status ("Setref failed: ..."), nothing changes.
- The menu is built only when it is read (`eff_rt.ref_menu`: three `findChildren` scans, memoised 0.5 s for the
  names + labels pair; 0.16 ms on b2 with 42 objects); a stored ref is the absolute path.
- **Existing projects:** `effectors.ref_upgrade()` in place (new eff_rt / menu_logic text, Addref / Refto / Setref
  in their page places, `eff_pulses` on Setref, the zkit panel refreshed and reopened if it was open; eff_list,
  objects and values kept; idempotent).
- Live b2 (31550): ref_upgrade twice (second: nothing added, list kept, 7 rows); Refto listed 42 objects + (none);
  through the panel: Target `zkm_new` (null) + Refto `zkm_rig/hand_r` + Setref -> ref `/project1/zkm_rig/hand_r`,
  own object hidden, packed centre texel 75 = (1.5, 0.5, 0) = the Null; Addref `hand_l` + Add sphere `zkm_born` ->
  born tied, no own object, texel 95 = (-1.5, 0, 0), and after moving the Null to (-0.75, 0.25, 0) texel 95 followed.
  Test effectors and the rig were removed after.

## Published rows (#pub) and inert rows (29 Oct 2026, drop-in round, lane A; live b2, TD 2025.31550)
User (29 Oct): "make sure everythings independent ... they should work if copy pasted in another project". The grey
reference lines into the user's PX_pointfx1 were every consumer -> `eff_rows` -> the `px_hot_px_pointfx1` row's object:
`eff_rows` read every row's worldTransform, **disabled rows too** (b2: `CONS/eff_in.dependenciesTo(px_hot obj)` was
non-empty with the row enabled AND disabled).
- **#pub:** a row another COMP publishes carries the tag `pub` (PX hot points `pxhot pub`, FX_track `track`, a
  module COMP's cloud / point set). `all` / `*` / empty Effselect = the user's own rows only: every non-pub row packs
  `OWN_BIT` (bit 23; user tags are now bits 0..22, `MAX_TAGS` 23) and `sel_vec('all')` becomes the mask `OWN_BIT`
  while any pub row exists (no pub rows: the old `all` flag, identical uniforms). Data only: no consumer recompiles.
  A published row is used only when named (`track`), tagged (`#track`, `#pub`) or as a bare tag word.
- **Two buffers, same layout and ids:** `eff_rows` packs disabled rows and #pub rows as placeholders
  (`effectors_logic.placeholder`: enabled 0, identity, no points, nothing of theirs read, so no dependency);
  `eff_rows_pub` packs #pub rows live and is read by the grid scatter / paint passes (now relative `../eff_rows_pub`)
  and by consumers whose Effselect reaches a pub row: `eff_in` = `eff_rt.rows_for(Effselect)`
  (`effectors_logic.wants_pub`). PX: `eff_use` 2 when a module names a pub row. Both CHOPs cook only when pulled.
- **Existing list:** `pub_upgrade()` (staged, PUB_GAP 10 frames, own window closed): p_texts (eff_logic / eff_rt /
  eff_grid), p_ops (eff_rows_pub), p_tags (its clock + `pub` on px_hot* / pxhot / FX_track track / a cloud-pts-actor
  row whose ref lies in a COMP with its own pages), p_grid, p_consumers (`pub_consumer`: every eff_in with the old
  expression), done; `pub_result()` in a later exec; second run `changed: []`. Rows are never removed or re-enabled.
- **Lane B builders with their own eff_in** (prox_mat `_eff_buffer`): they read `eff_rows` = own rows only (decoupled
  already); to select a pub row explicitly they adopt `effectors.EFF_IN_EXPR`.
- Live b2: pub_upgrade -> `changed` eff_logic, eff_rt, eff_grid, eff_rows_pub, `pub px_hot_pxf`, grid/paint_step,
  5 consumers; consumer -> hot object dependency gone, eff_rows_pub keeps it; `all` = 8388608 (OWN_BIT, all 0);
  `all #pxhot` -> eff_in = eff_rows_pub; second run `changed: []`, 0 errors. Tests `test/test_effectors_pub.py`.
