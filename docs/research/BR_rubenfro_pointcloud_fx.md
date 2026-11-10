# BR - Ruben Fro point-cloud / splat looks and a modular FX catalog for TouchDesigner (26 Oct 2026)

Offline research (no `td_*` call, nothing loaded in TD, no login, Instagram not opened). Feeds `/project1/lab/PX_pointfx`
(binding user rules: `docs/builds/px_requirements.md`: modules added/removed/duplicated, effectors are visible scene objects,
viewing preview with gizmos, wide ranges and "options and creative liberty"). Build: TD **2025.31550**, M1 Max, Rosetta, Vulkan/MoltenVK.
Tags: **[V]** I saw it (frames I extracted and read), **[S]** stated by a cited public page, **[K]** my background knowledge (no source
fetched; verify before relying), **[U]** unverified, **[T-nn]** our LEARNINGS (win over this file). Earlier files win where they overlap:
`BL_gaussian_splats_pointclouds.md` (splat formats, loaders, sort, renderers), `BO_particle_sims.md` (engine: POP vs compute-TOP state textures).
This file adds: the look targets, the technique behind each, and the module catalog with per-point maths.

Evidence on disk: `research_src/rubenfro/` (`meta/*.description` YouTube descriptions, `vid/` 720p-or-less downloads of a few public videos,
`frames/` contact sheets). Only his own public YouTube/site pages were used; **no assets of his are reused**, the looks are re-created
from our own scans/images (clean-room, look reference only).

## 0. Top findings

1. **Who/what [S]:** Ruben Frosali (RubenFro), Florence-born VFX artist/director, Tokyo since 2006, studio TRIDOT, Head of Cinematic at JADU AR;
   works in volumetric capture, point clouds, Gaussian splatting, "shader-driven particle systems"; **custom Unity tools** (his site
   `rubenfro.com/about`; XR AI Spotlight interview 14 Jun 2024). He is a Unity artist, not a TD artist: **no public TouchDesigner source, tutorial
   or breakdown by him exists that I could find**. The recipe below is reverse-engineered from his public videos + standard techniques, and
   every look maps to GPU maths we can write as compute GLSL.
2. **His look in one sentence [V]:** a *dark, night-time, teal-and-orange graded* scan of a real place, made of fuzzy overlapping points with
   *shallow depth of field and bokeh/lens-flare discs*, in which **chosen regions ignite** (saturated orange/white-hot, emissive, fraying into
   embers), **dissolve into drifting particles**, **stretch into streaks / a raw sampling lattice** and **re-condense**, under a gliding camera.
3. **"Proximity" in his work = a moving volume/point in the scan that changes what the points inside it do** (colour, emission, size, noise
   displacement, burn, dissolve). In the frames it is a person-shaped column of fire walking through the alley [V] and orange swipe fronts [V].
   That is exactly an SDF/distance-falloff effector with a falloff-driven material change; PX makes the effector a visible scene object.
4. **Everything he does is per-point maths on a static or sequenced point set** (rest position + colour from a scan). So the engine is: state
   textures (or POP attributes) + a stack of small functions + one render. The stack compiles to one compute pass per stage [T-46/T-47].
5. **Performance is the design constraint, not features:** additive glow rendering needs **no sort**; DOF as per-point CoC size (no post blur);
   effectors are O(N x E) analytic shapes (no neighbour search); default 1 M points, quality tiers to 4 M (section 5).

## 1. His signature looks (precise, with sources)

Frames read: `research_src/rubenfro/frames/NdCV/sheet_01.png`, `sheet_02.png` ("Dissolving Realities Vietnam #2", 60 s, 36k views, YouTube
id NdCVW1Ky0Js) and `frames/k4US/sheet_01.png` ("... Vietnam #3 - Real Time Point Cloud Shader in Unity 3D", 125 s, 17k views, k4USv2r444Q).
Descriptions are the uploader's own text (`meta/`). Also read: Dissolving Paintings (WXQwqDpWfcs) and Dissolving Lights Shibuya (do0x-4rNVEs) contact sheets. Downloaded but not read: Memories of Tsukiji, Leaving the Grid BTS, DAT 2 Kanda, Dissolving Alley (all in `vid/`, 720p or less); their looks are **[S]** from text only.

| ID | Look | What is on screen | Source |
|---|---|---|---|
| L1 | **Night scan, teal/orange grade** | Alley/market from a 360-camera photogrammetry point cloud; whole frame graded cold teal in shade with warm orange-amber light sources; deep crushed blacks; slightly milky haze | [V] frames NdCV, k4US; [S] "Photogrammetry captured with 360 cameras and running in real time in Unity using a custom geometry shader especially designed for cinematic rendering" (xz_dyCzZrFA) |
| L2 | **Point surface = fuzzy overlapping quads** | Surfaces are not clean meshes: dense soft-edged point sprites, visibly "crumbly" at silhouettes, bigger/blurrier near the camera | [V]; [S] "Unity geometry shader" (cKIhT70M2fU "Hanoi - 3D Photogrammetry Scan Unity Geometry Shader") |
| L3 | **Shallow DOF + bokeh + lens flare** | Background and foreground out of focus (blobs), purple/blue bokeh discs and flare ghosts around street lamps | [V] NdCV sheet_01, k4US sheet_01 |
| L4 | **Ignition / fire column on a person** | A person (scanned figure) turns into a column of white-hot to yellow to orange to red flame made of the same points: noisy ragged top edge, embers flying upward, bokeh embers in the air; the rest of the alley stays cold teal | [V] k4US sheet_01 rows 2-3; [S] tweet "Burning Gaussian Splat in Unity3D" 5 Oct 2023 (XR AI Spotlight) |
| L5 | **Orange swipe / local tint** | A region of the scan (floor, a sack, a figure) turns saturated orange/red, brighter, fuzzier, with streaks leaving it, then recovers | [V] NdCV sheet_01 bottom row, sheet_02 row 1 |
| L6 | **Edge fray / dissolve** | Roof lines and silhouettes break into particles that drift off; "fading memories that disintegrate when viewed up close" | [V] NdCV sheet_01 row 1 (frayed roof edge); [S] fakewhale profile; "Dissolving Alley People", "Dissolving Lights - Shibuya Underpass" ("floating lights deconstruct and dissolve 3D scanned locations at night") |
| L7 | **Lattice / streak collapse** | The scene collapses into a regular grid of red points stretched along the view axis, perspective lines radiating from the vanishing point (the scan's own sampling lattice), dark red monochrome, then re-forms to full colour | [V] NdCV sheet_02 rows 2-3 |
| L8 | **Camera fly-through with motion blur** | Smooth gliding camera through the scan, strong radial/motion smear on fast moves | [V]; "Flying through Hanoi streets in point cloud" (xz_dyCzZrFA) |
| L9 | **Paintings as particle sims** | [V] Dissolving Paintings (Great Wave): the painting is a regular grid of upright pillar/voxel points in a gilded frame (colour from the image, warm brass tone); a local disturbance throws the points out of the grid into a swirling crest of blue/white particles that then read as macro-DOF glitter bokeh; wide shot = framed picture floating over a sunset sea. [S] Starry Night, Klimt, Birth of Venus "[Glitchy]", Seurat "walkable point-cloud", Pearl Earring as voxels; Great Wave "real-time particle simulation in Unity, driven by a compute shader" | frames/WXQwqDpWfcs/sheet_01.png; dat.rubenfro.com/dissolving-paintings |
| L15 | **Shibuya underpass: wire/line scan** | [V] arched tunnel drawn as thin point-lines (ribs), blue-white light shafts, teal haze, pink-red scan patches fraying along the floor like brush strokes; single scene-change frame only (sheet has 1 cell) | frames/do0x-4rNVEs/sheet_01.png; "floating lights deconstruct and dissolve 3D scanned locations at night" |
| L10 | **Corrupted-data fragments** | "DAT" series: real-time photogrammetry of Akihabara/Kanda/Shinjuku as broken digital afterlife, data corruption, a character animated inside the scan | [S] UDU7jeY7Z0I, 6QkhS3V3Om0, N8dV0ekcvPY descriptions |
| L11 | **Splats as the new base** | Same effect library ported to Gaussian splats: burn, dissolve; splat processed in LichtFeld Studio after Metashape alignment; SHARP / World Labs for generated scenes | [S] XR AI Spotlight (14 Jun 2024; 2026 follow-up paywalled, intro only) |
| L12 | **Scale** | One piece animated from about 160 million points with a custom point shader (Shibuya railway underpass) | [S] his LinkedIn post (search snippet only) |
| L13 | **Data to sound** | For Dissolving Realities he converted point-cloud data to audio wave files | [S] XR AI Spotlight |
| L14 | **Stage use** | Large visuals for Sphere Las Vegas, Anyma AEDEN tour, Charlotte de Witte/Solomun/Mau P, Afterlife, Paul Kalkbrenner, Rezz, Perfume, Red Bull BC One, Meta "Deep Diving" (BnF Paris) | [S] rubenfro.com/about, /works titles |

Not found / not possible: his Instagram (login, not touched), Vimeo (200 OK for the profile but nothing parsed), `rubenfro.com/research`
(JS-rendered, empty), the 2026 Substack interview (paywall), any capture hardware list. Do not claim his exact shader code or parameters.

## 2. Techniques behind each look

| Look | Technique (what makes it) | Per-point ingredients |
|---|---|---|
| L1 grade | Split-toning / colour grade in post (shadows teal, highlights orange), gamma crush, haze via additive low-alpha fog, HDR emission then tonemap | colour, HDR gain, vignette |
| L2 fuzzy surface | Each point drawn as a camera-facing quad with soft Gaussian alpha (geometry-shader billboard = our instanced quad / splat), size from world radius / depth, colour from scan | size, alpha, colour |
| L3 DOF/bokeh | **Per-point circle of confusion**: `coc = A * |depth - focus| / depth`; draw quad of size max(radius, coc), alpha scaled by 1/(coc^2) (energy conserving) with a disc/hex texture; bright points above a threshold become flare discs | size, alpha, HDR colour |
| L4 fire | Noise-gated emission: heat = falloff(distance to figure) x noise(p*freq - t*rise); heat -> colour ramp black-red-orange-yellow-white; points with heat > threshold are displaced upward with curl noise and given life, spawned embers recycle | heat, velocity, life, size |
| L5 swipe | A moving plane/sphere/box effector; inside it colour is replaced/mixed with a tint, emission up, streak velocity | mask, colour |
| L6 fray | Noise-threshold dissolve: `n = noise(rest*f)`; `d = smoothstep(t-w, t, n + gradient)`; points with d active leave rest along curl noise with fade-out; edge points glow | alpha, velocity, edge mask |
| L7 lattice | Source points are sampled on a regular camera grid; stretch each point along the view ray by `k*speed` and clamp size to a thin line; monochrome tint; morph back by spring return | velocity-aligned stretch, tint |
| L8 | Camera path + motion blur from previous-frame position (trail) | prev position |
| L9 | Image -> points (one per pixel, depth from luminance/hue), then field-driven sim (wave, curl, spring return) | rest, velocity |
| L10 | Block glitch: quantise positions to a grid, random block offsets, channel shift, time-sliced frames | quantised P, hash |
| L11 | Splat: same maths, but alpha/scale come from the splat's own `opacity`/`scale_*`, modulated by the module outputs | scale, rot, opacity |
| L13 | Positions/colours as a sample stream -> Audio (we do the reverse: audio drives points) | audio bands |

Wider technique space (what the modules cover) and how artists do it, **[K] unless cited**:

- **Dispersion / dissolve:** noise -> step -> alpha is the universal dissolve recipe; for splats it is evaluated per splat from rest position and
  fed to opacity/scale ([web] search 26 Oct; SplatBridge ships five reveal patterns Scatter / FromPoint / Rain / Dissolve / Sweep, "3DGS Unity
  Shader Pack" is a splat FX system; both on radiancefields.com; source not read). Unity VFX Graph: spawn particles only where the dissolve
  front is, from a black/white channel map ([S] realtimevfx.com thread, Takfung, "inspired by RubenFro@youtube").
- **Photogrammetry / scan particles, morphing:** index-matched morph (sort both sets by a space-filling key or Hilbert/Morton code, lerp
  with noise delay), optimal-transport-lite by sorting along a random projection per axis.
- **4DGS / splat deformation:** per-frame splat sets (heavy), or deform by a displacement field/skeleton; for us: displacement from fields, **frame
  sequences of point textures** (M12), no per-splat re-training.
- **Proximity fields:** SDF of sphere/box/capsule/plane/torus/point-list/depth-silhouette, falloff `f = 1 - smoothstep(0, R, sd)`; per-effector
  falloff curves; combine by max/sum/smooth-min; Houdini "Attribute from Proximity / Point Wrangle `nearpoint`", Niagara "Get Distance to
  Static Mesh SDF", Notch "Particle Nodes: Attractors/Collisions" are the same idea.
- **Flows/attractors:** curl of a 3D noise potential (divergence-free), Lorenz/Aizawa/Thomas/Halvorsen attractors, 3D flow-field textures.
- **Audio reactivity:** band envelopes drive amplitude/pulse; transients trigger shockwaves; see `AC_audio_reactive_designs.md`, `K_audio_reactive.md`.
- **How artists build this in TD:** (a) POPs (Point File In POP -> Noise/Particle/Force POPs -> GLSL POP -> Geometry COMP instancing -> GLSL MAT;
  `glslPOP`/`glsladvancedPOP`: attributes are SSBOs, "Output Attributes" must be declared, `TDAttrib_<name>` read in MAT) [doc: derivative.ca
  Write_GLSL_POPs, GLSL_POP]; (b) compute-mode GLSL TOP holding state in float textures + GLSL MAT instancing (Gerritsen compute particles,
  `BO` 3.); (c) paid TDGS/GSOPs for splats (`BL`). Houdini: VEX wrangles + Karma/Redshift points; Notch: particle nodes + DoF post; Unreal Niagara:
  scratch-pad modules + SDF collision/Mesh Distance Fields; Unity: VFX Graph (GPU, properties/blocks) or custom geometry shader (his route).

## 3. Architecture for our system (what the catalog plugs into)

```
SOURCE (scan/ply/spz/depth/SOP)  ->  STATE textures: P0 rest, P pos, V vel, A aux(age,life,seed,heat)   (rgba32f, N = W*H points)
EFFECTORS (Null / box proxy COMPs, by path) -> table `effectors` (type, invWorldMatrix[4], size, falloff, id) -> uniform arrays (max 8)
STACK (tableDAT of modules, order = execution order)  ->  generator Python writes ONE compute GLSL per stage
   stage S1 MASK/FIELDS (compute rest-space masks into aux)      [optional, only if the stack has mask modules]
   stage S2 SIM        (forces, advect, spring, age/respawn)       reads+writes P,V,A in place (readwrite image, T-47)
   stage S3 SHADE      (colour, size, alpha, heat ramp)            writes C, S (colour+size+alpha texture)
RENDER: Geometry COMP instancing N quads (TDInstanceID -> texelFetch P,C,S) -> GLSL MAT (soft disc / splat / streak) -> additive -> Render TOP
POST: bloom/flare, grade, DOF is inside render (per-point CoC), grain, vignette -> OUT   |   PREVIEW: second camera adds gizmos (wire boxes, axes)
```

- **Add/remove/reorder/duplicate (R1):** the module list is a table; a module row = `(uid, type, enabled, effector_paths, params_json)`.
  Changing the row set rebuilds the GLSL text DAT once (hash compare; never per frame). Param values do **not** recompile: they live in a
  uniform vec array (`uMod[uid*8 + k]`) set from a Script/Constant CHOP (Math Mix scope expressions recompile per frame, F12 in BO). Two
  proximity modules with different effectors = two rows with different `effector_paths`.
- **Effectors are scene objects (R2/R3):** Null COMP (point, optionally with scale = radius) or Geometry COMP box/sphere proxy (visible in the
  preview). Python reads `op.worldTransform` (inverse matrix) + size each frame via a Script CHOP `effectors` -> 16 floats + size 3 + type. Box = SDF in the
  object's local space so rotation/scale work. Sphere/box/plane/capsule/point/torus supported; an extra "depth silhouette" effector samples a
  TOP in screen space (webcam/depth) for hands and bodies.
- **Drive/binding for every parameter (R4):** each param has `base` + optional `drive` = (source kind, channel, gain, offset, smooth). Sources: CHOP
  channel (audio band, LFO, MIDI, OSC), effector speed, effector distance to another effector, beat envelope, timeline.
- **Presets (R4):** a preset = module table + params + effector transforms as JSON; "morph between presets" = lerp of numeric params (module
  tables must match; otherwise crossfade renders with a Cross TOP at low quality). `Lag CHOP` smoothing like `zctl` (BE).
- **Engine switch** as in BO: `engine = compute | pop`. v1 = compute (proven on this Mac, T-47). POP engine = glslPOP chain, same stack text
  emitted in POP form (attributes `P`, `Cd`, `V`, `A`), gated until `td_perf` proves it.

## 4. MODULE CATALOG

Conventions. `p` = current position, `p0` = rest position, `v` velocity, `c` colour (HDR rgb), `s` size (world units), `a` alpha, `age`, `seed`
= hash(id), `t` time (s), `dt` frame step. `E` = effector (matrix, size, type), `sd(E,p)` = signed distance in metres (negative inside),
`fall(E,p,R,k) = pow(1 - smoothstep(0.0, R, max(sd,0.0)), k)` (1 inside, 0 beyond R). Each module lists **Params** `name [range] meaning`,
**In** inputs, **Math** per point. Module id prefixes: **C** core/material, **P** proximity, **M** motion, **K** masks/dissolve/lifetime, **T** triggers.
Every module also has the common params `enable [0/1]`, `amount [0..4] master gain (>1 allowed)`, `mask_in` (a mask id from K-modules or
none), `blend [add, mul, max, replace]`, and the common Drive per param.

### 4.1 Core render + material

**C0 Source** - points in. Modes: `scan_ply` (Point File In POP / Python decoder), `splat_ply_spz` (BL loaders; keeps `scale_*`, `rot_*`,
`opacity`, SH degree 0), `image_depth` (colour TOP + depth TOP, unproject: `p = (uv-0.5)*[w,h]*k + dir(uv)*depth*z`; one point per pixel; Depth
Anything via `camera_bridge`, BL 7), `video_depth` (live), `sop` (any SOP -> points), `grid/sphere/torus gen`, `sequence` (frames of point
textures for M12). Params: `count [1k..4M] decimate to N`, `scale [0.01..100]`, `rotate xyz`, `center (auto bbox)`, `flip y/z`, `seed`,
`density_pattern [random, blue-noise, every-nth]`. Outputs P0, C0 colour, optional normals (estimated from depth grid by cross of neighbours;
for unorganised scans from PCA offline in numpy).

**C1 Point renderer** - how a point looks. `mode [pixel_point, soft_disc, gaussian_splat, square, streak, voxel_cube, line_to_rest, custom_sprite]`.
Params: `size [0.0005..2] world`, `size_attenuation [0..1] (perspective vs screen-constant)`, `min_px [0..8]`, `max_px [1..512]`, `softness [0..1]`
(Gaussian sigma = 0.25..1 of radius), `aspect [0.1..10]`, `orient [camera, velocity, normal]`, `streak_len [0..50]`,
`blend [add, alpha, premult]`, `hdr [0..20]`. Math (vertex): `r = max(size*scale/ -viewZ*fy, min_px*pxsize)`; quad corners
`q in {-1,1}^2`; fragment alpha `a_f = a * exp(-dot(q,q) * (1/softness^2) * 2.0)` (gaussian) or `smoothstep(1,1-softness,|q|)` (disc).
Splat mode uses the covariance `Sigma = R S S^T R^T` projected with the Jacobian (as in the Gerritsen/ex7 vertex shader read in BL) to build
the 2D ellipse; fall back to disc when no `scale_*`.

**C2 Colour/material** - how colour is produced. `source [scan, ramp_by_attribute, solid, palette_by_id, normal_map, depth_fog]`;
`ramp_attr [height, depth, age, speed, distance_to_E, heat, noise, hash]`, `ramp` = 1D colour ramp (up to 8 stops, HDR), `tint` rgb,
`tint_amt [0..1]`, `saturation [0..3]`, `contrast [0..3]`, `exposure [-8..8] EV`, `emission [0..50]` (HDR multiplier of c), `emission_mask`
(fed by P/K masks), `fresnel [0..4]` (if normals: `pow(1-|dot(n,viewdir)|, f)` rim glow), `desat_far [0..1]`, `hue_shift [-1..1]`.
Math: `c = mix(scan_c, ramp(attr), tint_amt); c = hueShift(c, h); c = mix(vec3(lum(c)), c, sat); c *= exp2(exposure) * (1 + emission*mask)`.

**C3 Depth of field / bokeh** - per-point CoC. Params: `focus [0..200] m`, `aperture [0..2]`, `max_coc_px [0..200]`, `bokeh_shape [disc, hex, ring,
texture]`, `bokeh_bright [0..8]` (extra alpha for bright points), `focus_from [manual, effector_distance, nearest_E]` (rack focus onto an effector!),
`near_far_bias`. Math: `coc = aperture * abs(z - focus) / z * fy`; `r_px = max(r_px, coc)`; `a *= clamp((r0/r_px)^2, 0.02, 1)` (energy); bright
`c*=1+bokeh_bright*smoothstep(1,4,lum(c))*coc/maxcoc`. No post blur needed (cheaper than a TOP DOF pass).

**C4 Glow / lens** (post, TOP chain; GLSL compute TOPs each, T-47). `bloom_threshold [0..8]`, `bloom_intensity [0..8]`, `bloom_radius [1..64] px`
(6-level downsample/upsample), `flare_ghosts [0..6]`, `flare_dispersion`, `flare_halo`, `streak_anamorphic [0..1]`, `chromatic [0..0.02]`,
`grain [0..0.2]`, `vignette [0..1]`, `haze [0..1]` additive low-alpha fog by depth (milky blacks like L1).

**C5 Colour grade** - `split_shadow rgb`, `split_highlight rgb`, `balance`, `lift/gamma/gain`, `lut` (TOP 3D LUT or 1D), `tonemap [none, aces, filmic, reinhard]`,
`teal_orange` macro 0..1 (sets split-tone to the L1 look: shadows ~ (0.05,0.25,0.30), highlights ~ (1.0,0.55,0.20)). Applied after bloom, before OUT.

**C6 Trails / motion streaks** - previous-position store (`pPrev` texture). `mode [velocity_streak, camera_motion_blur, ghost_frames, persistence]`,
`len [0..2] s`, `fade [0..1]`. Math: quad stretched from `pPrev` to `p` (screen-space), alpha `*= 1/(1+len_px)`. Persistence = feedback TOP with
decay (cheap; only if the feedback op is clean on this Mac [T-46]; else streak geometry).

**C7 Camera rig** - `orbit/dolly/fly_path/handheld shake/lookat effector`, `fov`, `near/far`, path from CHOP/curve, `roll`, `shake [0..1]` (noise).
Preview camera separate (adds gizmos), same transform.

### 4.2 Proximity effectors (the signature)

Common params for all P-modules: `effectors` (list of paths; Null or box proxy), `radius R [0.01..50]`, `falloff_exp k [0.2..8]`,
`falloff_shape [smooth, linear, gaussian, step, ring, shell]`, `invert [0/1]`, `combine [max, sum, smin(k), product]` across effectors,
`use_effector_scale [0/1]`, `noise_edge [0..1]` + `noise_freq` (ragged edge so the volume is never a perfect sphere), `space [world, local_E]`.
All write a per-point scalar `w in [0,1]` (the proximity weight) that the module's action multiplies, and optionally publish `w` under a name
(`w_id`) so material/dissolve modules can read it (so "fire where the figure is" = P-module publishes, C2 ramps by `heat`).

```glsl
float sdSphere(vec3 q, float r){ return length(q) - r; }
float sdBox(vec3 q, vec3 h){ vec3 d = abs(q) - h; return length(max(d,0.)) + min(max(d.x,max(d.y,d.z)),0.); }
float sdCapsule(vec3 q, float hh, float r){ q.y -= clamp(q.y,-hh,hh); return length(q)-r; }
float sdTorus(vec3 q, vec2 t){ vec2 d = vec2(length(q.xz)-t.x, q.y); return length(d)-t.y; }
float sdPlane(vec3 q){ return q.y; }
float sdE(int i, vec3 p){ vec3 q = (uInvE[i] * vec4(p,1.)).xyz; // local space, scale/rotation honoured
  int ty = int(uEType[i]);  // 0 point,1 sphere,2 box,3 capsule,4 plane,5 torus
  float s = ty==2 ? sdBox(q, uESize[i].xyz) : ty==1 ? sdSphere(q, uESize[i].x) : ty==3 ? sdCapsule(q, uESize[i].y, uESize[i].x)
          : ty==4 ? sdPlane(q) : ty==5 ? sdTorus(q, uESize[i].xy) : length(q);
  return s * uEScale[i]; }                                       // keep loops bounded: uECount <= 8
float proxW(vec3 p, float R, float k){ float w = 0.; for(int i=0;i<uECount;i++){ float d = max(sdE(i,p),0.);
  w = max(w, pow(1. - smoothstep(0., R, d), k)); } return w; }
```

| ID | Module | Params (range, meaning) | Action per point |
|---|---|---|---|
| P1 | **Repel / Attract** | `strength [-50..50]` (neg = attract), `mode [radial, along_axis, tangent]`, `impulse_vs_force [force, impulse]`, `damping [0..20]`, `max_speed` | `dir = normalize(p - Ec)` (or gradient of SD by central difference); `v += dir * strength * w * dt`; clamp |v| |
| P2 | **Displace (pushed surface)** | `distance [-10..10]`, `along [normal, radial, axis, noise]`, `noise_amt`, `lag [0..1]` (points follow with spring so surface bulges and relaxes) | `target = p0 + dir*distance*w`; spring return handled by M6 |
| P3 | **Proximity dissolve** | `threshold [0..1]`, `soft [0..1]`, `noise_scale [0.01..50]`, `noise_gain`, `outward_speed [0..20]`, `scatter [0..10]`, `size_to [0..4]` (shrink), `fade_alpha [0..1]`, `edge_glow rgb`, `edge_width` | `n = fbm(p0*ns); d = smoothstep(th-soft, th, w + (n-0.5)*noise_gain)`; `a *= 1-d*fade`; `s *= mix(1,size_to,d)`; `v += (curl(p0*ns2)+dir)*outward*d`; edge `e = d*(1-d)*4` adds emission |
| P4 | **Colour by proximity** | `mode [tint, replace, ramp, heat, invert, hue_rotate]`, `ramp`, `emission [0..50]`, `ramp_range`, `flicker [0..1]` | `c = mix(c, ramp(w), amt*w)`; emission `*(1+emission*w)`; flicker `*= 1 + f*(hash(id,t*30)-.5)` |
| P5 | **Size / density by proximity** | `size_gain [-1..10]`, `alpha_gain`, `cull_below [0..1]` (points under w disappear), `grow_from_zero [0/1]` | `s *= 1 + size_gain*w`; alpha likewise; `if(w<cull_below) a=0` (reveal inside effector) |
| P6 | **Local time warp / freeze** | `time_scale_inside [0..4]`, `freeze [0/1]`, `echo_delay [0..2] s` | scales dt for M-modules per point: `dt_i = dt * mix(1, time_scale, w)`; freeze stores p when `w>0.5` |
| P7 | **Vortex / swirl** | `strength [-30..30]`, `axis [E_up, custom]`, `pull_in [0..5]`, `lift [0..10]`, `height_falloff` | `r = p - Ec; tang = cross(axis, r)`; `v += (normalize(tang)*strength + normalize(-r)*pull_in + axis*lift) * w * dt` |
| P8 | **Sweep / reveal front** (plane or box moved by the user or driven by T) | `front_width [0.001..5]`, `reveal_mode [hide_behind, hide_ahead, tint_front, burn_front]`, `invert`, `speed` (if driven by a timeline) | `w = 1 - smoothstep(0, width, abs(sdPlane(q)))` front band; `behind = step(0, -sd)`; combined with K1 for burning dissolves |
| P9 | **Stretch to streak** | `stretch [0..50]`, `axis [view, velocity, effector_axis, radial]`, `thin [0..1]`, `tint rgb`, `lattice_snap [0..1]` | `size.xy*=1/(1+thin*w)`; length `*= 1+stretch*w`; optional `snap p to grid(cell)` when `lattice_snap` (L7 lattice look: `p = mix(p, round(p/cell)*cell, w*snap)`) |
| P10 | **Magnet to shape** (morph points onto the effector's surface) | `pull [0..1]`, `shell_thickness [0..1]`, `keep_color [0/1]`, `jitter` | `p = mix(p, p - sd*gradSD, w*pull)` projection to the SDF surface; stays an object-shaped cloud around the effector |
| P11 | **Lens / magnify warp** | `magnify [-3..5]`, `chromatic [0..1]`, `swirl [0..6]` | `p = Ec + (p-Ec)*mix(1, 1/(1+m), w)` (spherical remap), colour fringe per channel |
| P12 | **Shockwave ripple** (ring wavefront from the effector on trigger) | `speed [0.1..50]`, `width [0.01..5]`, `amplitude [-5..5]`, `decay [0..5]`, `ring_color`, `max_rings [1..8]` | each ring i: `rr = (t - t_i)*speed`, `w = exp(-((d-rr)/width)^2)*exp(-decay*(t-t_i))`; `p += n*amp*w`; colour pulse |
| P13 | **Body / hands effector** (depth-cam / camera mask) | `source TOP`, `threshold`, `blur`, `depth_range`, `mapping [screen_projection, plane_at_z]`, `mirror` | project point to the source TOP uv (`uv = ndc(p)`), `w = texture(mask, uv).r` blurred by mipmap level; webcam clip `media/webcam/webcam_ref_5s.mp4` for tests |
| P14 | **Effector chain / trail** (point list from CHOP e.g. 8 hand joints or a trail of the effector's last N positions) | `chop`, `radius per point`, `smooth_union k` | `w = smax over points`; gives "paint with proximity" strokes that persist `trail_len` seconds (ring buffer in uniform array, max 64) |
| P15 | **Ignition / burn from proximity** (the L4 recipe packaged) | `heat_rise [0..10]`, `heat_decay [0..5]`, `ember_rate [0..1]`, `flame_noise_freq`, `flame_noise_speed`, `flame_height`, `ramp` (black/red/orange/yellow/white default), `smoke_amt`, `ash_color`, `hold_burn [0/1]` | persistent `heat` in aux: `heat += w*heat_rise*dt; heat -= heat_decay*dt`; `flame = heat * smoothstep(0.4,1., fbm(p0*f + vec3(0,-t*sp,0)))`; `c = ramp(flame)*emission`; `v.y += rise*flame`; `a *= 1 - smoothstep(1., 1.5, heat)` (consumed); embers spawn from burned points with life |

### 4.3 Motion fields

| ID | Module | Params | Math |
|---|---|---|---|
| M1 | **Curl-noise advection** | `strength [0..20]`, `scale [0.01..20]`, `speed [0..5]`, `octaves [1..6]`, `lacunarity`, `gain`, `bias_dir xyz`, `rest_pull` | `n = curl(P(p*scale, t*speed))` where `curl(F) = ∇×F`, F = 3 noise samples with offsets; finite diff eps 0.01*; `v += n*strength*dt`; or direct `p += n*dt` (kinematic); divergence-free so no clumping |
| M2 | **Flow field texture** (3D texture or 2D slice stack from TOP/CHOP) | `field TOP`, `strength`, `scale`, `world_box` | `v += (texture(field, (p-box.min)/box.size).xyz*2-1)*strength*dt` |
| M3 | **Strange attractor** | `type [lorenz, aizawa, thomas, halvorsen, dadras, chen]`, `a,b,c,d` per type, `scale [0.01..5]`, `blend_to_rest [0..1]`, `time_scale` | e.g. Aizawa: `dx=(z-b)*x - d*y; dy=d*x+(z-b)*y; dz=c+a*z - z^3/3 - (x^2+y^2)*(1+e*z)+f*z*x^3`; points move on the flow in attractor space `q = p*scale` |
| M4 | **Global forces** | `gravity xyz`, `wind xyz`, `wind_gust [0..1]`, `drag [0..20]`, `buoyancy [-5..5]`, `floor_y`, `bounce [0..1]` | `v += (g + wind*(1+gust*noise(t)))*dt; v *= exp(-drag*dt)`; floor reflects |
| M5 | **Shiver / jitter** | `amp [0..1]`, `freq [0..60]`, `per_point_phase`, `scan_noise [0/1]` (static hash jitter), `size_scale` | `p += (hash3(id, floor(t*freq))-0.5)*amp*w_mask` |
| M6 | **Spring return to rest** | `stiffness [0..200]`, `damping [0..50]`, `max_offset`, `rest_source [p0, morph_target]`, `delay_by_noise [0..2]` | `a = k*(p0-p) - c*v; v += a*dt; p += v*dt` (semi-implicit); delays by `noise(p0)*delay` give reforming waves |
| M7 | **Orbit / spin** | `axis`, `speed`, `falloff_with_radius`, `centre = effector/bbox` | `p = Ec + rot(axis, ang(|r|,t))*(p-Ec)` |
| M8 | **Waves / displacement** | `type [sine, ripple, standing, terrain_noise]`, `amp`, `freq`, `phase_speed`, `dir`, `normal_displace [0/1]` | `p += n_or_y * amp*sin(dot(dir,p0)*freq + t*speed)` |
| M9 | **Audio displace** | `band_map [low, mid, high, spectrum_by_height/radius/id]`, `amp [0..5]`, `smooth`, `beat_kick [0..5]`, `chop` | `p += n*amp*spectrum(bin(p0))`; bins from a 64-tap spectrum texture (1x64) |
| M10 | **Morph A->B** | `target_b` (second Source), `t [0..1]`, `match [index, morton_sorted, random_proj_sorted, nearest_grid]`, `noise_delay [0..1]`, `path [linear, curl_arc, explode_through_centre]`, `ease` | `u = clamp((t*(1+nd) - nd*hash(id))...)`; `p = mix(p0A, p0B, ease(u)) + curl*arc*sin(pi*u)`; colour mix likewise; matching done once offline in numpy on load |
| M11 | **Explode / implode** | `amount`, `centre`, `power`, `swirl`, `gravity_after`, `per_cluster [0..1]` (explode per colour cluster/ID chunk) | `d = normalize(p0-c); p = p0 + d*amount*pow(len,power)*(0.5+hash)`; |
| M12 | **Sequence playback (4D)** | `frames [point textures]`, `fps`, `loop`, `interp [none, linear, cubic]`, `time_offset_noise` | `p0 = mix(F[i], F[i+1], frac)`; "4DGS lite": per-frame position/colour textures, no per-frame splat training |
| M13 | **Glitch / block corrupt** (L10) | `block [0.001..2]`, `prob [0..1]`, `offset`, `channel_shift`, `quantize`, `hold_ms` | `blk = floor(p0/block)`; `if(hash(blk, floor(t/hold))<prob) p += hash3*offset`; quantise p to `block/n` |
| M14 | **Camera-lattice resample** (L7) | `grid_w,h`, `rebuild [0..1]`, `stretch_along_view` | re-sample cloud as `p = origin + dir(uv_cell)*depth(uv_cell)`; uses image_depth source; interpolates to lattice with `rebuild` |

### 4.4 Masks, dissolve and lifetime

Masks write a scalar `m in [0,1]` stored in aux or computed inline; any module's `mask_in` can use `m` or `1-m`.

| ID | Module | Params | Math |
|---|---|---|---|
| K1 | **Noise dissolve (+ burn edge)** | `progress [0..1]` (drive/timeline), `noise_type [value, simplex, worley, curl_mag]`, `scale`, `octaves`, `softness`, `edge_width`, `edge_ramp`, `direction bias xyz+amt`, `particle_release [0..1]`, `release_speed`, `release_curl`, `seed` | `n = fbm(p0*scale) + dot(p0,bias)*bamt`; `d = smoothstep(progress*(1+soft)-soft, progress*(1+soft), n)`; `edge = smoothstep(0,w,d)*(1-smoothstep(w,2w,d))`; emission on edge; released points advect M1 and fade |
| K2 | **Gradient dissolve** | `axis [x,y,z,radial,spherical,custom]`, `centre`, `range`, `progress`, `softness`, `noise_warp` | `g = dot(p0 - c, axis)/range`; `m = smoothstep(progress-soft, progress, g + noise*warp)` |
| K3 | **Image / video mask** | `TOP`, `projection [screen, planar, cylindrical, uv_from_source]`, `scroll`, `threshold`, `blur_mips` | `m = textureLod(mask, uv(p), blur).r` |
| K4 | **Lifetime / respawn** (ember system) | `life [0.1..60]`, `life_var`, `spawn_from [rest, masked_points, effector_volume, burned_points]`, `rate [0..1e6]/s`, `fade_in`, `fade_out`, `recycle_to [rest, random_rest]`, `kill_speed` | `age += dt; if(age>life){ p = p0_of(rand_index); v = 0; age = 0; life = life0*(1+(h-0.5)*var) }`; `a *= fadeIn*fadeOut`. Recycle pulls from the rest set so the cloud count is constant (no atomic float/append) |
| K5 | **Region cull** | `shape [box, sphere, plane, effector]`, `inside/outside`, `soft` | `m = 1-smoothstep(0,soft, sdE(i,p))`; uses same effector SDF |
| K6 | **Random thin / LOD** | `density [0..1]`, `by_distance_to_camera [0/1]`, `keep_near_E` | `keep = hash(id) < density*lodFactor` where lodFactor = `clamp(1 - (z-near)/far, 0.1, 1)` (also a perf knob) |
| K7 | **Attribute select** | `by [height, depth, hue, luminance, normal, id_range, cluster]`, `lo`, `hi`, `soft` | band mask from point attributes: layered looks (e.g. only floor burns) |
| K8 | **Mask combine** | `op [add, mul, max, min, subtract, xor]`, `inputs [mask ids]`, `invert` | builds a mask graph from other masks |

### 4.5 Triggers and drives

| ID | Module | Params | Meaning |
|---|---|---|---|
| T1 | **Audio envelope** | `source (Audio Device In / file)`, `band [20..20k Hz lo/hi]`, `attack/release [0..2] s`, `gain`, `gate`, `beat_detect [peak threshold, min interval]` | CHOP -> channel `env`, `beat`; any param drives from it |
| T2 | **LFO / noise** | `shape`, `freq`, `phase`, `random seed`, `sync_bpm` | CHOP channel |
| T3 | **Effector motion** | `speed`, `acceleration`, `distance_to(effectorB)`, `enter/exit event` | speed of an effector object (magnitude of dP/dt) is a modulation source: fast hand = more burn |
| T4 | **MIDI / OSC** | map CC/addr to param (reuses `td_midi_*`, `td_osc_*`) | |
| T5 | **Sequencer / timeline** | table of keyframes per param (`t, value, ease`), loop/ping-pong, preset recall times | drive + cues (`CQ_cuelist` BQ/TL timeline when built) |
| T6 | **Event -> action** | `on [beat, enter(E), exit(E), button, timeline_marker]`, `do [spawn ripple P12, start dissolve K1, flash, preset jump, burn ignite P15]`, `cooldown` | gate for one-shot effects (ripples, bursts) |
| T7 | **Preset morph** | `A`, `B`, `t`, `time`, `curve`, `per-module offset` | whole-look morph; numeric params lerp, enum params switch at `t=0.5` or crossfade |

### 4.6 Suggested starter stacks (presets that reproduce the references)

- **"Night alley" (L1-L3):** C0 scan -> C1 soft_disc -> C2 scan colour -> C3 DOF (bokeh_bright 3) -> C4 bloom + haze -> C5 teal_orange.
- **"Fire walker" (L4):** above + P15 Ignition on a Null that moves (T3 speed -> heat_rise) + M1 curl + K4 embers + C2 heat ramp.
- **"Fray" (L6):** above + K1 noise dissolve driven by P3 proximity of a box that sweeps through (P8).
- **"Lattice collapse" (L7):** C0 image_depth + M14 + P9 stretch (axis view) + C2 tint red + M6 spring return (delay by noise) + T1 beat -> `lattice_snap`.
- **"Paintings" (L9):** C0 image_depth from a painting rendered as upright voxel pillars (C1 `voxel_cube`, height = luminance) + P2/P1 disturbance effector throwing points into a P7 vortex crest + M8 waves + M1 curl + M6 return + T1 audio.
- **"Hand magic" (P13 body effector + P1 repel + P12 ripple on enter event)** for installations.
- **"Morph"** M10 between two scans with `curl_arc` path and K1 edge glow.

## 4b. Effectors in his videos and in two other references (YouTube study, 26 Oct 2026)

Method: `yt-dlp` list of the channel (about 70 videos; list in `research_src/rubenfro/yt/list.txt`), no transcripts exist (music/visual pieces, only
one auto-sub file, empty of content), descriptions saved per video. 12 of his videos watched as contact sheets (24 or 12 frames each, so one frame per
2-5 s; **timestamps below are +-3 s**) in `research_src/rubenfro/yt/<id>/s_*.jpg`; two user-supplied videos by **other creators** studied frame by frame
(1 fps) in `research_src/rubenfro/other/<id>/`. All tags are **[V]** (seen) unless marked. Not read: P7ekizIy8Rk, xz_dyCzZrFA (frames extracted only).
Nothing is shown of how he builds effectors (Unity, custom code); the table is what the picture does. Effectors are **never drawn as gizmos** in his
finals; they are invisible fields, apart from emissive objects (a fireball, a beam).

### 4b.1 Other reference A: "Point Cloud Animation city street" (PsLMv1T0gFw), 16 s, 24 fps, 1280x720

Creator **geronimo giqueaux** (channel "geronimo giqueaux", uploaded 2021-12-16, no description, no tags). Not Ruben Fro. A night street scan flown forward
by a gliding camera, graded orange/teal/pink; points are **chunky square/rectangular sprites with see-through holes**, no bokeh.

| t (s) | What happens | Effector / driver reading |
|---|---|---|
| 0-1 | Whole scene smeared into **vertical streaks hanging down from the top** (stalactites, orange/white/teal), a grey flat hole where the sky/ground void is; lower floor is crisp coarse dots | stretch along world Y with weight rising with height (a height band or plane sweeping, not a proximity ball): `prox_stretch` axis y, mask by height |
| 1-4 | Streaks **retract top-down**; by 3 s only the upper facades still frayed, shopfronts crisp, red awnings and a person (red shirt) readable; floor stays dotted | the stretch front is travelling downward with a **ragged hanging edge**: moving plane (path = line in Y, ~3 s), soft one-sided falloff (the side behind the plane stretched) |
| 4-8 | Clean scene, only jagged **tips on roof edges**; blocky sprites; camera forward and slight roll | residue of the front (low weight); coarse sprite size |
| 8-11 | Colour pushes to **magenta / teal / pink** by region (signs recolour), strong motion blur on the left side | per-region tint, `prox_colour` hue shift; velocity streak from camera motion |
| 11-14 | Buildings **thin out into sparse pink/white flakes**, sky goes black, density falls with distance and height | density / alpha by distance from the camera (`density` bydist) plus size shrink |
| 14-16 | Only a few flakes remain at the lower right, then black | global dissolve to nothing (`dissolve_time` / `lifetime`) |

Effector count: 1 (a sweeping slab) + camera distance. Visible: no. Response: stretch (long, thin, along one world axis), then reform, then fade out.

### 4b.2 Other reference B: "Kabukicho, Tokyo Red Light District | Pointcloud Render made in Blender | 8K" (InVn8fAmLj4), 15 s, 25 fps

Creator **sur.render** (channel "sur.render", uploaded 2023-01-21; Metashape + Blender, source footage from @Japanexplorer1; not Ruben Fro). Rendered offline
in Blender, 8K, so DOF and bloom are heavy. Camera is **rolled 30-90 degrees** and dives through the alley in a thick **orange volumetric haze**.

| t (s) | What happens | Effector / driver reading |
|---|---|---|
| 0-4 | Rolled fly-through; signs glow yellow, floor dark red; a violet/teal cast appears at 3 s (cold region, blue-green puddle-like patch on the ground); strong DOF blur | camera path + local colour regions (tint volumes), glow by emission on sign points |
| 4-8 | Dive; dark clustered figures (people as dense dark point blobs) at the alley mouth; signs saturate yellow-orange; fog grows | people stay as dark clusters, the rest burns bright: emissive tint on a scanned layer |
| 8-12 | **Blast**: whole frame goes white-hot yellow; the geometry is a **burst of faceted glass-like shards and streaks** radiating from the centre of the frame, prismatic colour fringes, bloom clipping | an expanding radial wave (shockwave) around the camera: strong push outwards + stretch radial + white emission; shards = large oriented flat sprites with chromatic fringe |
| 12-15 | **Re-forms**: alley returns in orange haze; **dark debris chunks** (flat torn slabs, red/black) lie on the floor and drift near the camera; signs lit again | chunked leftovers (the scanned people dissolved into dark scraps), slow drift, density low near the camera |

Effector count: 1 (blast sphere at / near the camera), plus the camera itself as the viewpoint. Visible: no (the white flash hides it).

### 4b.3 Ruben Fro: effectors in the videos (table)

Ids: DAT3 = N8dV0ekcvPY, KANDA = 6QkhS3V3Om0, ALLEY = gAZp2fWjsko (+ Tokyo/Hanoi pieces), DR1 = sGRA6Q7BgDo, TSUKIJI = HeaP23cp8J8, VN4 = EuAqCf63VXE,
FUT = hO11eQzN9Ec, DONGX = YHCQpbERF-8, LTG = xFBSwJ8NZ9Y, plus the earlier NdCV/k4US/WXQw/do0x frames in section 1.

| Video, t (s) | Effector type | Response seen | Falloff / timing |
|---|---|---|---|
| KANDA 0-15 | **Animated scanned person** (a character animation, Nathan Thomas) walking away down the alley, made of the same points | its outline is a sparkle/point halo, lit from behind; trails off as it walks; a cyan light blob next to it | the effector is a moving **point set** (a mesh/actor sequence) that is also drawn |
| KANDA 25-45 | **Swipe front on the left of frame** (a plane moving across the scan) | behind it the wall turns **cream-white then red, then returns to green**; the edge is fine sparkles and fraying dust, 2-3 colour bands | one-sided falloff (sharp front, long recolour tail), edge noise high frequency, front crosses in ~15-20 s |
| KANDA 45-60 | Scene itself bends | the alley is **curved into a spiral/tunnel** (space warp along the view axis), lantern bokeh and lens flare | smooth bend growing with distance along the axis, no particles move apart |
| KANDA 60-100 | **Fire fronts on the walls** (vertical regions at the lower right and along both walls) | wall points turn red-orange, fray into tall flame sheets and **embers lifted upward**; green leaves remain untouched | high flame-noise, rises with height, front travels along the alley |
| KANDA 100-120 | An **emissive fireball point** (bright, with a glowing core, drifting at lower left) | surroundings shred into flat **leaf-like slabs** floating in black, embers trail the ball; ends as a few shards | visible light object that leaves a trail; global dissolve to scraps |
| ALLEY 0-3 | **Rising jets** at each person | dense teal-white sparkle columns streaming up, red fire layer behind | upward force + emission, per-person effector |
| ALLEY 6-9 | Person effector | body turns into **spikes / feather shards** pointing outward; a signboard becomes **white wire ribbons in a helix**; an orange starburst erupts at the feet | radial spike (stretch along normal) + line render of surfaces; burst at a foot position (a second small effector) |
| ALLEY 9-19 | Person effector + large fire | a huge **billowing red/orange flame cloud** (curl noise, much larger than the person) surrounds a **voxelised (cube-blocks) figure** with a white-hot core; glowing **path lines** converge on the vanishing point on the floor | points emitted from the effector volume into a bigger cloud; figure snapped to a cube lattice; floor lines = stretch to lines along the path |
| ALLEY 20-22 | Everything | white-yellow radial **explosion**, points stretched radially | global radial stretch, <1 s |
| DR1 (Dissolving Realities 1) 17-35 | **Thin cyan horizontal slab / beam** crossing the alley, visible as light | local cut: points on the beam glow cyan, rest orange-sepia tinted regions along walls | plane effector, narrow shell falloff, visible emissive proxy |
| DR1 26 | Scanned person | **cube-pixel body** (green), blocky |  lattice snap on the person only |
| DR1 40-52 | Floor region | wet green floor with **rising sparkles** (emission + upward lift), then **white wavy lines** laid on the floor and steps (waves propagating across the ground) | wave module on a plane effector; thin line stretch |
| DR1 62-70 | Vendors (people) | **orange-fire fringe** on a woman and the stall goods while the rest stays cold green-teal | ignite on person (point set or body mask) |
| DR1 80-85 | A scanned motorbike and rider | **sliced into horizontal ring bands** (stripes with gaps), turning slowly | slice quantisation along an axis (stepped bands) |
| DR1 86-96 | Whole scene | warp-speed **radial streak to the vanishing point**, yellow/white, then bloom white-out; at ~100 s everything **collapses to a tiny cluster on a red glow** | stretch from the view centre, then magnet-to-point with progress, the same cluster opens the piece at 0-5 s |
| VN4 0-5 / 50-58 | Whole scene | city built of **flat rectangular tiles / slabs** that float and rearrange, then snap into the full neon street | chunked displacement: points move in groups (tiles), not one by one |
| VN4 15-35 | Vendors and a flag | figures turn **solid orange points**, near-camera points become **huge soft bokeh discs** (grow when close) | tint by point set, size by camera distance (CoC), bokeh rim |
| TSUKIJI 16-28 | Passer-by / moving object | a **sparkle splash** erupts beside the lane, a warm **white-orange fireball** at lower left, a campfire-like pit at the bottom (~39 s) | moving local sources with emission; no trails |
| DAT3 0-12 | Whole field | points become **long thin needles** fanning from the vanishing point (a "grass field", 20 M strings), red/yellow sparks (short streaks) sprinkled | stretch along view/radial axis, per-point length by id |
| DAT3 22-35 | Whole field | **red vertical lattice** of stepped columns, then **hot orange scanline rows** (horizontal, stepped, perspective), finally **teal cuboid voxels / pillars** with a floor tile grid | lattice snap in 3 axes one after another (cell, snap), colour ramp by stage |
| DONGX 0-70 | Static **fire cone** fixed at the left (a fountain of streaks rising to a white-hot tip), red bokeh discs floating | the shop front behind **shivers** (points jitter, regrow), the cone itself is the effector (emitter) | emitter with fountain velocity, constant emission; background jitter low |
| FUT 15-40 | Local hot patch | a small **orange hot patch** on a blue-monochrome street, blue glitter points all over, quantised cubes | colour replace by region, sparkle rate by density |
| LTG (BTS) | Left side column | vertical **red/white flame column** in the dark alley, cyan sparkle on trees, shown beside the source footage | tall box effector, upward flame noise |
| NdCV/k4US (section 1) | Person-shaped column of fire; swipe fronts; lattice collapse | see L4, L5, L7 | as section 1 |

### 4b.4 Top 10 effector findings

1. **Effectors are mostly fields, not objects you see:** sweeping planes/slabs (KANDA swipe, geronimo stretch band, DR1 cyan beam), a person-shaped column, a bend of space. Only emissive fireballs/beams are drawn.
2. **Persons / moving actors are the main effector** (KANDA walker, ALLEY, DR1, VN4): an animated point set that ignites, spikes, pixelates or leaves sparkle trails.
3. **One-sided falloff** is the signature of fronts: sharp leading edge, 2-3 colour bands behind (cream, red, back to green) with a sparkling ragged edge.
4. **Stretch has many axes**: world Y (hanging streaks), radial from the vanishing point/camera (needles, warp speed), along a floor path (glowing lines) and radial from a body (spikes).
5. **Quantisation is a response**: cube lattice (person, DAT3 voxels), horizontal bands/slices (bike rings, scanline rows), tiles/slabs that move in groups (VN4, KANDA 100 s).
6. **Fire is bigger than the scan** (ALLEY, DONGX, KANDA): flames/embers are emitted into empty space from a person, a cone or a wall, not just recoloured scan points.
7. **Space itself is an effector**: bend/spiral of the alley (KANDA 45-60 s), radial blast around the camera (sur.render 8-12 s), camera dive; the camera position/forward drives radial effects.
8. **Timing is slow and staged**: fronts take 15-20 s, stretch retracts in ~3 s, blasts <1 s, openings/closings use a collapse to / burst from a tiny cluster (DR1 0-5 s and 100 s).
9. **Near-camera points grow to bokeh discs** and lens flare ghosts accompany emissive objects (VN4, KANDA, TSUKIJI).
10. **Few effectors at once (1-3 big + a few small)**, but a point-set effector counts as many; no hand/face/sound/path effector is visible in these clips (no evidence of sound-driven effectors; his data-to-sound is the opposite direction).

## 4c. What PX must add (coverage checklist, vs docs/builds/px.md and px_requirements.md)

Rule: reuse or extend existing modules first. Columns: points / splats: ok = the existing module does it on that type; **needs** = the stated addition is
required for that type. Splat meaning of the five channels: centre (move), scale/covariance (grow, shrink, stretch along an axis), opacity (dissolve),
colour/SH0 (recolour), rotation (swirl, align). Current PX v1 renders splats as **discs of mean scale** (px.md "Known risks"); real anisotropic splats are
the first splat gap (S1 below).

| Look (source) | Covered by | points | splats | Missing -> minimal addition |
|---|---|---|---|---|
| Fire column on person, ignite (NdCV/k4US, DR1, ALLEY, VN4) | `prox_burn` + `prox_colour` emissive, effector = body mask / points | ok | needs S2 | person as point-set effector (A1) |
| Swipe front with 2-3 colour bands (KANDA 25-45) | `prox_colour` ramp + Plane effector, `dissolve_gradient` | partial | partial | one-sided falloff shapes `behind` / `ahead` (A3) and an effector path (A2) |
| Hanging vertical streaks, retract (geronimo 0-4) | `prox_stretch` | partial | needs S3 | stretch **axis** par [view / world axis / effector axis / radial from effector or camera / velocity]; mask `mask_attr` by height (exists) |
| Needles / radial warp streak / glowing floor lines (DAT3, DR1, ALLEY) | `prox_stretch`, `velocity_streak` | partial | needs S3 | same stretch axis par (radial-from-camera); line thinness `thin` already |
| Lattice / voxels / cube bodies (L7, DAT3, ALLEY, DR1) | `prox_stretch` snap + cell | ok | needs S4 | for splats: snap centre and set scale = cell, rotation = identity; sprite **cube** (shaded) for points |
| Horizontal slices / scanline rows (DR1 bike, DAT3) | none | missing | missing | `prox_stretch` mode `slices`: band along axis, alternate bands offset or hidden (gap 0..1, stepped); one param set, no new module |
| Tiles/slabs moving in groups (VN4, KANDA 100 s) | `explode`, `dissolve_*` per point | missing | needs S5 | header par `chunk` (cell size 0..2) on modules that use noise/hash: points in one cell share the random value; sprite **oriented quad** (uses point normal or splat rotation) |
| Flames/embers larger than the scan, cone fountain (ALLEY, DONGX, KANDA) | `prox_burn` embers (only from burned scan points) | partial | partial | `prox_burn` `source` [scan / effector volume / effector surface] + `Pool` share of Count reserved for spawned points (initial velocity cone, life, curl, ramp); splat scenes spawn **point-sprite** embers from the pool |
| Space bend / spiral alley (KANDA 45-60) | `twist` | partial | partial | `twist` mode [twist / bend], axis `view`; for splats also rotate each splat by the same local rotation |
| Radial blast / shockwave around camera (sur.render 8-12) | `shockwave`, `explode` | ok | needs S3 | effector kind **camera** (live render camera as an effector); splats: shards = large flat splats (scale x,y up, z thin) |
| Dissolve to flakes by distance/height, fade-out (geronimo 11-16) | `density` bydist, `dissolve_*`, `lifetime` | ok | ok | for splats opacity + scale shrink (S2) |
| Near-camera bokeh discs, flare ghosts (VN4, KANDA) | Look DOF, bokeh rim, bloom | ok | needs S6 | splats need their own CoC blur in the splat shader; add `flare` (ghost + streak) to Grade (one param group) |
| Visible emissive proxy: fireball, cyan beam (KANDA 100, DR1 17-35) | gizmo only in preview | missing | missing | effector option `glow` (colour, intensity, size): the effector shape is drawn into the output as additive light (A5) |
| Shiver / jitter of the background (DONGX) | `jitter` | ok | ok | (splat: jitter centre, keep covariance) |
| Collapse to / burst from a tiny cluster (DR1 0-5, 100) | `prox_magnet` pull 1, `explode` progress, Source Morph | ok | ok | none |
| Wire ribbons, wavy floor lines (ALLEY 6-9, DR1) | `wave` + `prox_stretch` thin | partial | partial | covered by the slice/stretch modes, no line renderer needed in v1 |
| Animated actor inside the scan (KANDA walker, ALLEY people) | none (single static source A/B) | missing | missing | Source **Actor layer** (A4) |
| Peel, push, swirl, glow, trail, reform (section 4.2 P1-P15) | the 30 modules | ok | needs S1-S3 | see S list |

### What to add to PX (the concrete list)

**A. Effector system (px_eff, px_rt)**
- **A1 Point-set effector kind** `pts` (already required as item 8 in px_requirements; not in px.md Effectors yet): sources CHOP xyz, TOP xyz, another source's
  state texture (the **Actor layer** below), mesh vertices, depth cam; returns nearest distance (<= 1-4 k brute force, else a splatted 2D/3D distance grid),
  plus **per-point effector velocity** (frame difference).
- **A2 Effector motion (paths)**: per-effector `motion` [none / line A-B / circle / lissajous / chop path / noise wander / follow Null], speed, loop, ease; a front
  crossing the scene in 15-20 s must be a parameter, not hand keyframes. Existing drive sources `espd` stay.
- **A3 Falloff shapes + wake**: add `behind`, `ahead` (signed, one-sided for planes/fronts) and `wake` (sharp front, long tail along effector velocity) to the shape list;
  a `trail N` ring buffer (8..64 past positions) per effector for sparkle trails.
- **A4 Actor layer** (Source, not a module): a second point/splat source with its own transform, play (sequence / depth cam / generator) and `layer` mask, rendered with the
  main cloud; it can be selected as a point-set effector (A1) so a walking figure ignites, spikes or pixelates the scan around it.
- **A5 Effector visibility**: per effector `glow` (colour, intensity, size, trail) drawn into `out1` as additive light; default off. The preview gizmos stay.
- **A6 Effector kind `camera`**: the render camera position + forward as an effector (radial blast, bend axis `view`).
- Count: raise from 8 only if A1 needs it; a point-set effector is one slot.

**B. Module parameter changes (extend, no new modules)**
- `prox_stretch`: add `axis` (above), `mode` [stretch / lattice / slices], `gap`, `bandwidth`; `cell` already.
- `prox_burn`: add `source` [scan / effector volume / effector surface], `Pool %`, `cone`, `speed`, `lifespan`; keep `consume`.
- `twist`: add `mode` [twist / bend], axis `view`.
- header (every module): `chunk` (shared random value per cell); falloff shape list gains `behind / ahead / wake`.
- Look: sprite `cube` and `quad` (oriented by normal / splat rotation); Grade: `flare`.
- Everything else (push, vortex, dissolve, colour, size, magnet, jitter, shockwave, curl, wave, density, lifetime, masks) is unchanged.

**C. Splat parity (points and splats both; needs S = splat work in the render and sim passes)**
- **S1 Anisotropic splats** in the render: v1 draws discs by mean scale (px.md known risk). Needed: 2D covariance from scale xyz + quaternion (state texture already keeps both), depth sort
  (BL_splat_render sorts 228 k at 60 fps), Count tiers lowered for splats (<= 500 k).
- **S2 Opacity + scale in every shade module:** dissolve = opacity down and scale down; peel = scale to 0 along the surface normal axis then move; recolour = DC colour (SH0) only, higher SH bands fade out with the effect amount.
- **S3 Stretch on covariance:** stretch along the axis (A/B above) = scale x (1 + stretch*w) along that axis expressed in splat space (rotate axis into splat frame), thin the other two; shards = scale z -> 0.
- **S4 Rotation:** vortex/twist/bend rotate each splat by the field's local rotation (quaternion multiply), snap = identity rotation, chunk/tile = one shared rotation per cell.
- **S5 Embers from splats** use the Pool as ordinary point sprites (no covariance) with the splat colour; flames are never splat-based.
- **S6 Splat DOF**: CoC blur in the splat footprint (+ bokeh rim by opacity), otherwise bokeh discs do not appear on splat scenes.
- After any module that moves centres, the splat sort runs on the new positions (or the sort is skipped under an additive-only style).

**D. Presets worth shipping after the above**: "KANDA swipe" (plane front + ramp), "Hanging streaks" (geronimo), "Alley people fire" (point-set + burn pool), "Radial blast" (camera effector), "Slice bike", "Tile city".

## 4d Coverage audit 27 Oct

User (27 Oct ~01:20-01:30): "i wanna be able to do everything that rubenfro does and all", "including the green lines,
volumetric haze nd glow and all", "ability to change colors", "ability to place lights geometry in 3d space and it should
effect the splats". Offline (no TD). The 4b study covered 12 videos; this pass adds **12 more of his public YouTube videos**
(descriptions via `yt-dlp --write-info-json`, 360p downloads, contact sheets 4x4; no login, no bot-protection bypass,
Instagram / X / Behance not opened: they need a login or block scripted access). Evidence: `research_src/rubenfro/yt2/`
(`<id>.info.json`, `<id>.description`, `<id>/s_NN.jpg`, `vid/`). Sheets have no burnt-in time: **cell k of a sheet at step
s starts at (sheet_index x 16 + k - 1) x s seconds, +- s/2**; times below are computed that way. All [V] unless marked.
Result table + build plan: `docs/builds/RUBENFRO_COVERAGE.md`.

New videos read (id, date, length, his own description in short):
TFM = sOAtKBoqMrg "Through Fragmented Memories" (10 min, LED premiere 13 x 60 ft 3D LED screen, Mynt NYC Oct 2021; uploaded
2025-11-11; step 10 s), AVA = yMWYSn6lIiI "Avatara" (2023, "Gaussian Splat 3D capture, running in Unity 3D"; step 4 s),
GM42 = pGdtnpOdOAo "Generated Memories AE 1942" (2025-10-28, "Gaussian splat worlds created with WorldLabs"; step 4 s),
TRS = JTelWwnGPGs music video with Ital Tek ("exploding and extruding point clouds", Hanoi; step 5 s), F49 = FvSzPq1G_PM
"FRAGMENT #49.3" ("particle effects and aesthetic of the TV series Devs"; step 5 s), P459 = H1Fkram-qns "Approaching Planet
45.9" (Meteor Crater lidar, 30 M points, Unity real-time VFX; step 2 s), SPRWL = UHttYL-jJ-8 "SPRWL77" (step 4 s),
BTNA = bzykZvofX4U "Through the Night, Between the Atoms" (360-camera photogrammetry + "special shader ... Future Cities";
step 6 s), BA2 = pv0f0Iy1rHM "BackAlleys Fragment 2" (step 6 s), OSC = d2sTvz4lm3M "Unity VFX processing OSC signals from
live coding session with SonicPi" (step 17 s). Descriptions only: DESCENT (oFkc1dOsZvQ, 23 min short for ASUS / ACRONYM;
credits "TYPOGRAPHICS: David Rudnick", vehicle / drone / character models = meshes inside the scans), Shibuya Takeover
(W4m5kgudn0M, Shibuya mega screens Nov 2020), Future Cities train (omeRP047akk), Chiang Mai (gpTHY_zMnJY), Mother,
KANDA ULTRAWIDE (ciN9oeZ2aZY: "highest field of view"), Dancing Spheres (V9G07jHMnnE: vertex shader driven by SonicPi over OSC).

### 4d.1 The "green lines" (thin bright neon line overlays): which kinds he uses
| Kind | Where (time) | Behaviour |
|---|---|---|
| **Concentric neon rings** around a subject | TFM 40-60 s (3-5 green rings, thick bright core + wide glow, around a chrome figure; rings scale outward), TFM 600-620 s (green rings orbit a chrome figure, tilted ellipses), BTNA 78-90 s (white ring + wire logo), OSC 119 / 187 / 238 s (rainbow chromatic ring halo over the pillars) | 2-6 rings, line width ~0.5-1 % of frame, strong bloom, not occluded by the scene, slow scale / orbit; one colour per piece (green, white, rainbow) |
| **Edge / outline lines tracing the scan** | TFM 320-370 s (orange-gold neon outlines along shop fronts, floor edges, sign frames, the rest dark), BA2 84 s (green neon lines on stair edges and door frames), BA2 42 s and 90 s (a person drawn as white outline lines), TFM 250 s (green line-drawn meditating figure) | lines sit on depth / colour discontinuities of the scan; thickness constant in pixels; glow; they appear and fade per region, so they are masked (fronts / proximity) |
| **Light-trail ribbons on the ground** | TFM 140 s, 230-290 s (rainbow / red / blue streak lines running along the street to the vanishing point), ALLEY 9-19 s (4b) | long, thin, curved, many parallel; they flow forward with the camera; colour by line (rainbow) |
| **Slice / contour lines** | TFM 240-260 s (magenta heads drawn as horizontal stripes), Shibuya underpass (L15 ribs), DR1 40-52 s (white wavy floor lines), BA2 30 s (teal ribbed wall lines) | equal spacing along one axis, thin, emissive; waves can travel along them |
| **Line vortex / tendrils** | TFM 410 s (spiral of curved line strokes on black), BA2 78 s (red lightning-like line tangles converging on the camera) | strokes are long trails of moving points (streamline look), noisy, hot core |
| **Wireframe polylines / graphics** | BTNA 84-90 s (polygon wireframe logo), DESCENT credits (typography) | a SOP / vector drawn as glowing lines |
| **Sweep beam** | DR1 17-35 s (thin cyan slab crossing the alley, 4b) | a plane of light with a sharp core |

### 4d.2 Haze, light and glow
- **Volumetric haze / shafts:** BTNA 0-6 s (a white waterfall-like light column with bokeh discs and a lit haze around it),
  TRS 40-45 s (magenta light column in fog, then the whole frame washes to a milky white bloom), P459 6-30 s (crater in
  sunset haze with distance fog, ends in a white fog-out), TFM 70 s (red / teal haze of out-of-focus light), GM42 48-60 s
  (green film-graded haze over a splat city). His haze is **depth-based and coloured by the nearest lights**, not a flat lift.
- **Lights in the scene:** P459 (5 glowing orbs hovering over the terrain, lighting the ground around them), OSC
  (cyan tube lights in the ceiling, pillars glowing from inside), TFM 110 s (a falling column of light). Emissive objects
  carry their own bloom and lens rings (BA2 6 s / 90 s ring flare; OSC rainbow ring).
- **Glow:** strong multi-scale bloom on emissive points (fire walls TFM 130-200 s, SPRWL 4-16 s where flames clip to white),
  bloom on neon signs, chromatic ring flares (OSC, BA2), rainbow arcs (TFM 230 s), film-like halation in GM42.
### 4d.3 Other techniques found (new vs 4b)
- **Meshes inside the scans:** chrome / glossy objects (giant chrome hands TFM 200-210 s, chrome heads and figures TFM
  10-60 s and 600-620 s, a red balloon TFM 220 s, reflective suit BA2 48 s), vehicles / drones / characters in DESCENT
  [S credits]. They occlude the point cloud and the cloud occludes them; they reflect the neon scene.
- **Glyph tiles:** AVA 12-28 s: the splat scan breaks into glowing cubes with letters / symbols on them (typography in
  points), after a magenta palette inversion (AVA 8 s).
- **Palette remaps:** AVA 8-12 s (magenta / purple inversion), TFM 420-430 s (acid yellow / magenta / cyan remap),
  GM42 (green-red film split tone), F49 (monochrome).
- **Downward extrusion:** TRS 55-70 s (the alley extruded into long stalactite streaks) = Hanging streaks (4b).
- **Radial zoom smear burst:** GM42 16-32 s, TRS 75 s (white radial burst).
- **Reassembly from fog:** F49 0-15 s (the scan condenses out of a cloud of points; reverse at 65-70 s); 360 equirect output.
- **Strands:** P459 6-10 s (lidar points drawn as oriented blades / feathers, like grass).
- **Falling drip / rain of bokeh:** BTNA 24-66 s (red bokeh drops falling from shop fronts).
- **Whirlpool tunnel:** TFM 300-310 s, 560-590 s (the train interior twisted into a teal whirlpool around the camera axis).
- **Audio sync:** OSC (hex floor tiles light and pillars rise on hits sent from Sonic Pi over OSC), Dancing Spheres [S].
- **Ultrawide / fisheye:** KANDA ULTRAWIDE [S], BA2 (barrel lens ring).
- **Generated splat worlds as source:** GM42 [S WorldLabs], continuing L11.

Sources (27 Oct): https://www.youtube.com/watch?v=sOAtKBoqMrg , https://www.youtube.com/watch?v=yMWYSn6lIiI ,
https://www.youtube.com/watch?v=pGdtnpOdOAo , https://www.youtube.com/watch?v=JTelWwnGPGs ,
https://www.youtube.com/watch?v=FvSzPq1G_PM , https://www.youtube.com/watch?v=H1Fkram-qns ,
https://www.youtube.com/watch?v=UHttYL-jJ-8 , https://www.youtube.com/watch?v=bzykZvofX4U ,
https://www.youtube.com/watch?v=pv0f0Iy1rHM , https://www.youtube.com/watch?v=d2sTvz4lm3M ,
https://www.youtube.com/watch?v=oFkc1dOsZvQ , https://www.youtube.com/watch?v=W4m5kgudn0M ; profile
https://xraispotlight.substack.com/p/exploring-volumetric-art-with-ruben (Unity, point-cloud libraries ported to splats).
Not reachable without a login: Instagram, X, Behance project pages.

## 5. Performance notes (M1 Max, TD 2025.31550 under Rosetta, MoltenVK) 

Facts that bind the design: T-46 (pixel-mode multi-pass GLSL TOP chains tear), **T-47 (use compute-mode GLSL TOPs; 441/441 clean)**, T-35
(out-of-bounds in GLSL can crash the app: clamp every `texelFetch`, bound every loop), BO 5 (no ray queries, no double, no float atomics;
Math Mix scope expressions recompile every frame; wrap time hashes), F14 (bare render of 2M sprites 60 fps, 4M 38.6 fps, 10M 11.5 fps at 7488x2880).

1. **One compute dispatch per stage, never more.** Stack compiler merges all modules of a stage into one `main()` and reads/writes state once
   (read P,V,A -> apply module functions in order -> write). 3 stages max (fields/mask, sim, shade). Do not make one GLSL TOP per module.
   State in `rgba32f` textures (P, V, A, plus P0/C0 static). 2048x2048 = 4.19 M points = 3 x 64 MB = 192 MB of state (fine on 32 GB unified); 1024x1024 = 1.05 M default.
2. **Compile once.** The generated GLSL text lives in a Text DAT; rebuilt only when the module table changes (hash). Params flow through uniform
   arrays driven by a CHOP, never through `Scope` expression changes. Show a "compiling" flag and keep the old output until the new shader cooks cleanly.
3. **Proximity = analytic SDF loops: O(N x E x modules).** With E <= 8 and 4 proximity modules that is ~32 sdf evals per point: 1 M points x 32 =
   32 M evals/frame, trivially cheap compared to fill. Share `w` between modules (compute once per effector set per frame in S1). No neighbour/kNN
   search anywhere (that would need a grid hash with atomics we lack); fake local interaction with fields (M2) if ever needed.
4. **Render cost is fill, not point count.** Additive soft sprites with large bokeh radii overdraw heavily: cap `max_px` (default 64), and let
   CoC discs above ~24 px fade alpha by `(r0/r)^2`, so cost per frame stays near-constant. At 1080x1920 (2.07 MP) fill is ~10x lower than at
   7488x2880, so F14's counts are conservative **[U: remeasure at 1080x1920]**.
5. **No sorting needed for additive/premultiplied-additive blending** (order-independent); sort (Sort POP radix or CPU radix 5 ms/1 M, BL) only for
   `alpha` blend mode and true splat compositing. Default blend = additive; this is why we avoid the bitonic multi-pass trap (T-46) entirely in v1.
6. **Quality tiers (a `Quality` par, rebuilds nothing):** `draft 256k` (`K6 density` + 512 texture, preview/dev), `std 1M`, `high 2M`, `max 4M` (only with
   other lab COMPs parked). Bloom at half resolution; glow uses 6 downsample levels, not a large blur kernel. Target <= 3 ms COMP cook (CLAUDE.md 60 fps rule); report cook ms + fps via `td_perf`.
7. **Preview vs output:** the gizmo preview is a second render of the same instances at `draft` density or just effectors + a decimated cloud (no
   second full render). Output TOP is clean. Preview viewer is on while building (T-49) but timing is measured with it off, others parked.
8. **Python stays out of the per-frame path** except the effector Script CHOP (<= 8 matrices, trivial) and the T-modules; no `numpyArray()` per
   frame on the big textures (T-48). Loading/decoding scans and morph matching run once in the arm64 helper (`camera_bridge`) or numpy at import.
9. **Source loading:** `.ply` via Point File In POP -> to texture with `poptoTOP`/`toptoPOP` (31550 has both); `.splat/.spz` via our decoders
   (BL 5.1); big scans (100 M+, like his 160 M Shibuya piece) are not real-time here: pre-decimate offline (voxel/random) to the tier counts.
10. **POP engine as the option:** `glslPOP`/`glsladvancedPOP` writes `P`, `Cd`, `V`, custom attrs as SSBOs and a Geometry COMP instances them to the
    GLSL MAT, same stack text. POP loops carry an open macOS crash class (BO 3), so compute-TOP engine ships first; run the POP engine on the scratch TD first (`tools/scratch_td.py`).
11. **Things to avoid:** Line MAT width (no effect on macOS), `double`, float atomics, `rayPOP`, per-frame DAT-to-array conversion of big tables,
    cookRate changes (T-64), feedback chains until verified (T-46), 4+ K dispatches per frame, destroying ops that a pane shows (T-70).

Suggested live checks (numbers to record when built, none exist yet): R1 1 M points + C1+C2 only fps at 1080x1920; R2 +4 proximity modules x 4 effectors; R3 DOF with max 64 px;
R4 bloom; R5 4 M tier; R6 add/remove module recompile hitch ms; R7 effector transform latency (frames); R8 hands-effector (P13) with the webcam clip.

## 6. MCP tool ideas (not added)

`td_px_module(add|remove|move|dup, module, params)`, `td_px_effector(add_null|add_box|link, module)`, `td_px_preset(save|load|morph)`,
`td_px_perf()` (cook ms per stage + fps), `td_px_import(path)` (decimate + decode + auto-centre scan). All typed wrappers around one COMP table.

## 7. Build order proposal (for the PX builder, hours are estimates)

1. Engine skeleton + C0 (ply + image_depth) + C1 + C2 + additive render + preview camera with gizmo (3-4 h). Pilot: one scan from `~/ComfyUI-Shared/output/sharp_*.ply` or the Hornedlizard sample, 1 M points.
2. Stack compiler (table -> GLSL text) + effector Script CHOP + P1, P3, P4, P5 (3 h).
3. K1 dissolve + M1 curl + M6 spring + K4 respawn (2 h). 4. P15 ignition + C3 DOF + C4 glow + C5 grade (3 h). 5. T-modules + presets + controls panel (2-3 h).
6. M10 morph, M12 sequence, P12/P13/P14, M13/M14, splat covariance mode (later).
Parallel lanes safe: GLSL function library (pure text, testable offline with numpy ports + pytest), controls UI, preset/JSON schema.
Offline-testable: stack compiler output text; effector SDF numpy ports vs expected values; curl divergence ~0; dissolve monotonic in `progress`.

## 8. Done / not done / open questions

Done: public-source research, frames read for four of his videos, catalog. Not done: Instagram (login), the paywalled 2026 interview, four downloaded clips not yet read, nothing run in TD. `vid/` and `frames/` are research evidence; `vid/` is large (~190 MB), delete after study if space is needed.
Open: (1) which look to build first (suggestion: "Fire walker", the most distinctive); (2) should P13 hands use webcam live or the stored clip; (3) POP engine
in v1 or later; (4) include splat covariance mode in v1 (needs `.ply` with scale/rot) or discs only.

## Sources

- YouTube study (26 Oct): channel https://www.youtube.com/@RubenFro (videos listed in `research_src/rubenfro/yt/list.txt`); other references https://youtu.be/PsLMv1T0gFw (geronimo giqueaux), https://youtu.be/InVn8fAmLj4 (sur.render).
- RubenFro site: https://www.rubenfro.com/about (bio, tools, clients, works list), https://www.rubenfro.com/works (titles only; project pages are JS-rendered, empty).
- Fakewhale profile: https://log.fakewhale.xyz/?p=11957 (Dissolving Realities / Future Cities / custom shaders; "disintegrate when viewed up close").
- XR AI Spotlight interview 14 Jun 2024: https://www.xraispotlight.com/blog/exploring-volumetric-art-with-ruben-frosali-from-point-clouds-to-gsplats/ ; 2026 follow-up (paywalled intro): https://xraispotlight.substack.com/p/3dgs-workflows-for-unity-and-ar
- Dissolving Paintings: https://dat.rubenfro.com/dissolving-paintings/ ; YouTube channel https://www.youtube.com/@rubenfro (descriptions saved in `research_src/rubenfro/meta/`).
- Real Time VFX thread (VFX Graph point-cloud study, "inspired by RubenFro@youtube"): https://realtimevfx.com/t/unity-vfx-graph-study/12688
- Splat tools with dissolve/FX patterns: https://radiancefields.com/splatbridge-brings-streamed-gaussian-splats-and-splat-colliders-to-unity-6 , https://radiancefields.com/3dgs-unity-shader-pack , GSOPs https://radiancefields.com/gsops-brings-native-gaussian-splatting-to-touchdesigner
- TD GLSL POP docs: https://derivative.ca/UserGuide/Write_GLSL_POPs , https://derivative.ca/UserGuide/GLSL_POP ; Noise POP lesson https://learn.derivative.ca/courses/100-fundamentals/lessons/109-pops-working-with-points/topic/working-with-the-noise-pop/ ; Interactive & Immersive HQ GLSL particle/curl noise course (paid, not read) https://pro.interactiveimmersive.io/courses/glsl-particle-simulation-in-touchdesigner-capstone/
- Our files: `BL_gaussian_splats_pointclouds.md`, `BO_particle_sims.md`, `AC_audio_reactive_designs.md`, `BE_rudiment_zerror.md`, `docs/builds/px_requirements.md`, LEARNINGS T-35/T-46/T-47/T-48/T-49.
