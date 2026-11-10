# PX point-cloud / splat FX — user requirements (26 Oct 2026)

Binding for the design, prep and live build of `/project1/lab/PX_pointfx` (see `docs/research/BR_rubenfro_pointcloud_fx.md`).

1. **Modular:** effect modules can be **added and removed** at any time (not just toggled), in any order, and
   duplicated (e.g. two proximity modules with different effectors). The enabled stack compiles into one GPU pass per
   stage; changing the stack recompiles once, never per frame.
2. **Effectors are objects in the scene:** every proximity / field / mask module is driven by **Null COMPs** or by
   visible **square / box proxy objects** (Geometry COMPs) that the user can see in the preview and move, rotate and
   scale. Their transforms (and size, for boxes) feed the module (no hidden numbers only). Effector objects can be added
   and removed per module; a module points at its effector(s) by path.
3. **A viewing preview:** a preview camera render that shows the cloud **and** the effector objects as gizmos
   (wire boxes / axes for Nulls), separate from the clean output TOP (the output carries the look only).
4. **Options and creative liberty** (user rule): wide parameter ranges, many modes, material controls, presets that
   morph between whole looks; no built-in limits.
5. Look references: Ruben Fro (https://www.instagram.com/rubenfro/) — see the research doc.
6. **Gaussian splats are first-class** (user, 26 Oct: "gaussian splatting too"): every module works on splat scenes
   (.ply / .splat / .spz, via the BL_splat_render loader) as well as plain point clouds, acting on what a splat has:
   centre (move), scale/covariance (grow, shrink, stretch along motion), opacity (dissolve), colour/SH (recolour),
   rotation. Splats keep rendering as real anisotropic splats (depth-sorted, as BL_splat_render does: 228k splats at
   60 fps) - never downgraded to dots when an effect is on. Splat-specific looks: splats peeling off a scan by
   proximity, drifting embers from a splat scene, splat dissolve to dust, splat morph between two scans.
7. **No bloat** (user rule): modules share only what 2+ of them actually use; no framework beyond the module stack.
8. **Point-set effectors** (user, 26 Oct: "proximity can be just points too - like in ruben fros videos"): an effector
   can be a SET OF POINTS, not only a box/sphere/plane/Null: face/hand landmarks (FT_face_track CHOP), depth-camera
   points (DC_depth_cam), another point cloud or splat scene, BO_particles state, a mesh's vertices, any CHOP/POP/TOP of
   xyz. Proximity = falloff from the NEAREST point (or a soft sum/density with a kernel), with the same falloff shapes,
   combine modes and ragged edges. Up to ~1-4k points brute force in the compute pass; larger sets go through a GPU
   distance/density field (splat points into a 3D grid or 2D screen-space JFA, then sample) so it stays ~60 fps.
   Velocity of the effector points (frame difference) can drive wakes/pushes (points stirred by a moving hand).
   Applies to PX modules and to the mesh proximity material (MX_prox_material).

## 9. From his videos (effectors)

Source: `docs/research/BR_rubenfro_pointcloud_fx.md` sections 4b/4c (12 Ruben Fro videos + two other references: geronimo giqueaux PsLMv1T0gFw, sur.render InVn8fAmLj4).
Goal (user): PX does everything shown there, on **point clouds and Gaussian splats alike**. Extend existing modules first.

1. Effector kind **point set** (`pts`): CHOP/TOP/mesh/depth/another source/actor; nearest distance + per-point effector velocity.
2. **Effector motion paths** (line, circle, lissajous, CHOP, noise wander, follow) with speed/loop; fronts that cross the scene in 15-20 s.
3. Falloff shapes `behind`, `ahead`, `wake`; effector `trail N` ring buffer.
4. **Actor layer** in Source (second point/splat source with its own transform/play) usable as an effector.
5. Effector `glow` (draw the effector as additive light in the output, default off) and effector kind `camera`.
6. `prox_stretch`: `axis` [view / world / effector / radial from effector or camera / velocity], `mode` [stretch / lattice / slices], `gap`.
7. `prox_burn`: `source` [scan / effector volume / surface] + `Pool %` of spawned points (cone, life), embers from splat scenes as point sprites.
8. `twist`: mode `bend`, axis `view`. Header par `chunk` (points move in groups). Look sprites `cube`, `quad`; Grade `flare`.
9. **Splats parity:** real anisotropic splat render (covariance from scale + quaternion, depth sort), opacity + scale in dissolve/peel, stretch on covariance,
   per-splat rotation from vortex/twist/snap, splat DOF; every look in the checklist works on both types.
10. **Performance (v1 measured 26 Oct: draft 65k = 6.3 ms, std 131k = 7.4, high 262k = 9.0, 1M = 17.2; per-frame Python
    engine 1.2-1.4 ms; stack edit hitch 40-144 ms).** v2 must: move the per-frame Python engine to CHOP/expression
    uniforms or one tiny Script CHOP (target <= 0.2 ms/frame); cut render cost (cheaper sprite path, no per-point
    branches for unused materials, early-out of dissolved points, half-res glow); targets with PX as the hero look:
    std 131k <= 4 ms, high 262k <= 6 ms, splat scene 228k at 60 fps; stack-edit hitch < 30 ms if feasible (otherwise
    report). Measure with the other lab COMPs parked. (Status 26 Oct: perf pass done on scratch, results + what is still
    over and why: `docs/builds/px.md` "Perf pass".)
11. **Proximity + effectors everywhere** (user, 26 Oct: "proximity and effectors needs to be in splats nd all"):
    (a) in PX every proximity module and every effector type (objects, point sets, paths, actor layer, camera) works on
    Gaussian splats exactly as on points (splats stay real splats); (b) the SAME effector objects drive the other COMPs
    too, using the shared maths in builders/glsl/px_common.glsl (already shared with MX_prox_material): BL_splat_render
    and BL_cloud_morph (proximity reveal/dissolve/push), BO_particles (forces: push/attract/vortex/kill/spawn near
    effectors), BN_fluid2d (inject dye/force at effectors), BN_cloth (colliders + grab), GN_reaction_diffusion /
    GN_physarum (already have effector Nulls: align to the same effector format), FX_destroy (burn/shatter start at an
    effector). One shared effector set: /project1/effectors (Nulls, boxes, spheres, planes, point-set refs) that any
    COMP points at by path; no per-COMP copies of the maths.
12. **Modular effector set** (user, 26 Oct: "i want it modular so if i want i can add more effectors in it"):
    effectors are a LIST the user grows: an "Add effector" control (kind menu: box / sphere / plane / capsule / Null /
    point set / path / camera / actor), remove, duplicate, rename, enable, per-effector falloff + gain + gizmo; each
    consumer (PX module, MX material, adapters) picks effectors by name or tag ("all", "hands", ...). **No fixed cap of
    8:** pack effectors into a data texture (one row per effector) read in a loop sized by a uniform count, so any
    number works and cost scales; recompile never needed when adding/removing effectors.

**Design + adapters for items 11 + 12 (shared list `/project1/effectors`, packed buffer, PX v2 contract):
`docs/builds/effectors.md`.**
