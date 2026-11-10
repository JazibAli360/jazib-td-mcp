# effectors

> Shared effectors: `/project1/effectors` + adapters (26 Oct 2026, TD 2025.31550)

v0.3.0 - TD 2025.31550 - exported 2026-10-27 03:25:54 from `/project1/effectors`

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

Build doc: `docs/builds/effectors.md`

## Inputs / outputs

- none

## Custom parameters

### Effectors

| name | label | style | default | value |
|---|---|---|---|---|
| Addkind | Kind to add | Menu | sphere | path |
| Addname | Name (empty = kind + n) | Str |  |  |
| Addtags | Tags (space separated) | Str |  |  |
| Add | Add effector | Pulse | False | False |
| Target | Effector (for the pulses below) | Str |  |  |
| Remove | Remove | Pulse | False | False |
| Duplicate | Duplicate | Pulse | False | False |
| Newname | New name | Str |  |  |
| Rename | Rename | Pulse | False | False |
| Toggle | Enable / disable | Pulse | False | False |
| Track | Update rows | Menu | frame | frame |
| Sync | Sync objects to the list | Pulse | False | False |
| Status | Status | Str |  | 4 effectors, 4 enabled, 0 lights on, 0 envs on, 0 point texels |
| Listver | List version (auto) | Int | 0 | 22 |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |

### Lights

| name | label | style | default | value |
|---|---|---|---|---|
| Palsource | Palette | Menu | neon_trio | neon_trio |
| Palstops | Custom stops (hex [pos], comma separated) | Str | #00ff66 #00e5ff #ff00cc | #00ff66 #00e5ff #ff00cc |
| Palmode | Palette mode | Menu | steps | steps |
| Palinterp | Blend | Menu | oklab | oklab |
| Palshift | Palette shift (drive me) | Float | 0.0 | 0.0 |
| Palreverse | Reverse palette | Toggle | False | False |
| Lightcolsrc | Light colour source | Menu | solid | solid |
| Lightpalpos | Palette position | Float | 0.0 | 0.0 |
| Lightpalspread | Palette spread (x attribute) | Float | 1.0 | 1.0 |
| Lightkeep | Keep source colour | Float | 0.0 | 0.0 |

### Grid

| name | label | style | default | value |
|---|---|---|---|---|
| Gridon | Distance field on (cloud effectors) | Toggle | False | False |
| Gridcentrex | Grid centre | XYZW | 0.0 | 0.0 |
| Gridcentrey | Grid centre | XYZW | 1.0 | 1.0 |
| Gridcentrez | Grid centre | XYZW | 0.0 | 0.0 |
| Gridsize | Grid size (cube edge, world units) | Float | 4.0 | 4.0 |
| Gridres | Field resolution (voxels per edge) | Menu | 32 | 32 |
| Gridalpha | Cloud point valid when alpha > | Float | 0.5 | 0.5 |
| Painton | Paint volume on | Toggle | False | False |
| Paintres | Paint resolution | Menu | 64 | 64 |
| Paintselect | Paint with (names / #tags) | Str | #paint | #paint |
| Eraseselect | Erase with (names / #tags) | Str | #erase | #erase |
| Paintrate | Paint rate (full / s at weight 1) | Float | 2.0 | 2.0 |
| Paintdecay | Fade (per s, 0 = stays) | Float | 0.0 | 0.0 |
| Paintclear | Clear paint | Pulse | False | False |
| Paintfile | Paint file (project folder) | Str | paint/effectors_paint.exr | paint/effectors_paint.exr |
| Paintsave | Save paint | Pulse | False | False |
| Paintload | Load paint | Pulse | False | False |

## Perf

cook 19.518 ms (CPU 19.518 / GPU 0.016) summed over the 3 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "effectors", "parent": "/project1/lab"}` (lands parked)
