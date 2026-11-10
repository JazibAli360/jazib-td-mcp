# FX5. Generative styles and artist looks, as buildable TD 31550 effects (research, 26 Oct 2026)

Offline research. TouchDesigner was not touched (no `td_*` call), nothing built, downloaded or installed. Target: TD 2025.31550, macOS under
Rosetta, Vulkan/MoltenVK, 1080x1920, 60 fps, about 3 ms per COMP (`CLAUDE.md`).

**Evidence grades.** `[src]` = read or returned by a web search/fetch on 26 Oct (URL in section 9). `[mem]` = standard published maths or
technique I know, not re-fetched today. `[design]` = my own build plan, no source shows it working in TD. **Every perf figure is a
`[design]` estimate for a later measurement pass, not a claim** (the only measured numbers in this repo are in `O_generative_simulations.md` and
`E_live_rig.md`; GPU compute share has no Mac measurement yet). The web searches for artist techniques returned thin material (marked per
artist); where a technique is "how the look is achieved" rather than "how the artist did it", the text says so.

## 0. Summary

1. **38 effects (G01-G38)** in five groups: A fields/lines/attractors, B tiles/automata/growth, C cells/blobs/SDF/fractals, D mirror/op-art/data-viz,
   E artist looks (10 emulations, technique only, no assets). Priority 1 = build first for live visuals.
2. **Almost all of it is one pattern**: a state texture + one compute-mode GLSL TOP per step (T-47), or a POP particle system + additive Render TOP.
   Pixel-mode multi-pass is avoided (T-46). Nothing here needs Optical Flow (T-18), float atomics, doubles or hardware ray tracing.
3. **Already covered, extend rather than rebuild**: particles/curl (`BO_particles`), fluid (`BN_fluid2d`), cloth, splats, point-fx (PX), face track,
   palette map, motion trail, strobe, test pattern. td-port already holds `kaleido`, `tunnel`, `tile`, `halftone`, `ascii`, `echo`, `glitch`,
   `ripple`, `flow_fx`, `ink_flow`, `rutt_lines`, `prism_glass`, `beam_fx`, `light_shafts`, `slit_scan`, `shatter`, `pixel_fx` (pending/unrun in TD
   unless the INVENTORY says a .tox exists). Section 7 lists per-existing-effect extensions.
4. **Licence rule** (from `L_shader_sources_licences.md`): Shadertoy default is CC BY-NC-SA 3.0, so nothing is copied from it without a header
   saying MIT/CC0; IQ's SDF snippets are MIT (`[src]` iquilezles.org articles page, quoted in L), but his shader *art* is not. Everything here is
   a clean-room build from published maths. Artist works are emulated by technique; no frames, logos or assets are reused.
5. **Photosensitivity** is the real show risk for this topic: moire, gratings, Ikeda-style black/white flicker and stripe-regime automata are
   the classic triggers. Every effect in D and E that can flicker gets a `Safe` par (rate cap, contrast cap) wired to the strobe COMP's limiter.
6. **Recommended first wave (all priority 1, mostly S/M):** G03 attractor dust, G06 Truchet family, G08 CA lab, G12 blob field, G13 SDF scene toolkit,
   G17 op-art/moire, G18 ridgeline, G19 XY phosphor scope, G20 data barcode, G28 domain-warp ink, G30 recursive split, G34 ribbon brush.

## 1. Platform constraints that decide every design

| Constraint | Source | Consequence for this topic |
|---|---|---|
| Multi-pass pixel GLSL can show unfinished inputs on this Mac | T-46 | Write every multi-step look (CA, JFA, Laplace growth, LIC) as compute-mode GLSL TOPs (T-47: 441/441 clean) |
| No Optical Flow TOP | T-18 | No video-motion-driven field; drive fields from frame difference, person mask, depth cam, face landmarks, audio |
| No float atomics, no double attributes (macOS doc) | O s1 | Scatter-accumulate (attractors, flames, DLA walkers) = **additive Render TOP of points**, not atomicAdd; deep fractal zoom needs two-float emulation (G14) |
| Particle/Feedback POP loop has an open crash class | O F11 | Run any POP-loop effect through the scratch TD first (T-83) |
| 60 fps / 3 ms per COMP | CLAUDE.md | Every effect gets `Quality` (0.25/0.5/1 of 1080x1920), a cook-gate and a baked fallback loop |
| 2 M sprites at 24 px hold 60 fps at 7488x2880 | E (O s1) | 1080x1920 has 10.4x fewer pixels; point-count budget for particle effects starts at 1-2 M, `[design]` |
| Text TOP shapes Urdu, no HarfBuzz | BJ | Data-viz labels use Text TOP; no custom shaping needed |

**Shared module conventions** (every effect, per the user's "modular, many options + presets, no built-in limits" rule): custom pars on the COMP
(`Seed`, `Speed`, `Quality`, `Palette` (feeds `FX_palette_map`), `Audio` gain/band, `Reset` pulse, `Safe`), `Out` Null, optional `Effector`
Null(s) (position + radius + strength rows, same table as PX), preset DAT with 6-10 named presets, `zkit` controls, stage plan stored per COMP.

## 2. Group A. Fields, lines, attractors

### G01 Flow-field streamlines (curl / Perlin / image-gradient field) - P1, M
- **Look**: thousands of fine glowing lines flowing along an invisible field, trails fading; "silk" / "hair" / wind-map look (Tyler Hobbs-style flow fields; Fidenza is a flow-field work `[mem]`).
- **Technique** `[mem]`: field F(x,y,t) = rotate(grad(noise)) or curl(noise) or gradient of an input TOP luminance; N agents step `p += F*dt`, wrap/respawn at edges or by age; draw as short oriented segments or accumulate trails in a feedback TOP.
- **TD build** `[design]`: two modes. (a) POP: reuse `BO_particles` with Noise POP `NoiseCurl2` (F5 in O) + Trail POP, additive Render TOP. (b) Pure TOP: state texture of agent positions (RGBA32F 512x512 = 262k agents), compute pass 1 = advect + respawn, compute pass 2 = splat via Render TOP point sprites (no atomics), Feedback TOP + Level for fade. Field source selector: curl noise / `Field` TOP input / person mask gradient / audio-driven rotation.
- **Pars**: Count 1k-2M; Field scale 0.1-8; Octaves 1-6; Curl/gradient/angle-quantised mode (angle snapped to 4/6/8 directions = circuit-board look); Speed 0-4; Life 0.2-20 s; Line width 0.5-6 px; Trail fade 0.9-0.999; Turbulence in time; Palette by angle, speed or age.
- **Presets**: Silk, Hair, Circuit (angle snap), Wind map, Oil (high fade), Rain (field = down + noise).
- **Inputs**: Field TOP, mask TOP (spawn only inside a person), audio band -> field rotation speed, effector Null -> vortex.
- **Perf** `[design]`: 262k agents ~1-2 ms, 1 M ~3-4 ms (trail feedback at full res adds ~0.5 ms). **Extend** BO_particles (new `Mode: Streamlines`).
- **Not possible**: real motion-vector fields from codecs; use frame difference or a depth-gradient instead.

### G02 Line Integral Convolution ink (LIC) - P2, M
- **Look**: a texture "combed" along a vector field: brushed-metal, hair, wood grain, fluid-ink streaks; the stills version of G01 and cheap.
- **Technique** `[mem]`: for each pixel, average a noise texture along the streamline (±L steps of RK2 through F). Animate by sliding the noise phase along the flow.
- **TD build** `[design]`: single compute GLSL TOP, 24-64 taps, input noise TOP + field TOP; no state. Colour by field magnitude via palette map.
- **Pars**: Length 4-64 taps, Step 0.5-3 px, Noise grain 1-8 px, Phase speed, Field source (as G01), Contrast, Sharpen.
- **Presets**: Brushed steel, Combed hair, Ink wash, Wood. **Perf** `[design]`: 48 taps at 1080x1920 ~1 ms. **Reuse**: fluid2d velocity field as input = "Anadol ink" (E1).

### G03 Strange attractor dust (3D) - P1, M
- **Look**: slow orbiting luminous ribbons/dust shaped by Thomas, Aizawa, Halvorsen, Lorenz, Dadras, Chen, Sprott, Rossler, Rabinovich-Fabrikant; hypnotic, compact. (A Derivative tutorial "Strange attractors (POPs)" Aug 2025 exists `[src]`; equations from dynamicmath.xyz `[src link only]`; the Attraktors Designer community app mixes attractors `[src]`.)
- **Technique** `[mem]`: integrate dp/dt = f(p) per particle (RK2/RK4, 2-8 substeps), thousands of particles seeded in a small blob so they trace the manifold; colour by speed/age; slow orbit camera.
- **TD build** `[design]`: GLSL POP (Thomas first: bounded, cheapest) with `npasses` as substeps, variants selected by a `vec` uniform (never an expression in Scope, F10 in O); Render TOP with Point Sprite MAT, additive; re-seed guard when |p| > R or NaN.
- **Pars**: Attractor (menu 10), Parameter a/b/c (each with range from the system; Thomas b 0.18-0.2 is the calm regime `[mem]`), Substeps 1-8, dt 0.001-0.05, Count 50k-2M, Point size, Colour by speed/age/axis, Orbit speed, Trail length, Audio -> dt and one parameter through a 2 s Lag.
- **Presets**: Thomas silk, Aizawa torus, Halvorsen petals, Lorenz wings, Dadras knot. **Perf** `[design]`: 1 M points ~2 ms. **Notes**: parameter sweeps cross chaos/limit-cycle boundaries, so audio modulation is clamped.

### G04 2D attractor density maps (Clifford / de Jong / Pickover) - P2, S-M
- **Look**: delicate smoke-and-lace filaments, astrophysical dust, glowing log-density images.
- **Technique** `[mem]`: iterate x' = sin(a y) + c cos(a x), y' = sin(b x) + d cos(b y) (Clifford) for millions of points; accumulate hit counts per pixel; display log(density) through a colour ramp.
- **TD build** `[design]`: no atomics, so draw points additively into a float16/32 Render TOP, then a compute pass does log-tonemap + palette. Millions of points via a POP seed re-iterated each frame from last frame's position state (state texture).
- **Pars**: a,b,c,d (-3..3, with random-walk drift), Iterations/frame 1-16, Points 0.5-4 M, Exposure, Gamma, Palette, Symmetry fold 1-8.
- **Presets**: Lace, Smoke, Starfield. **Perf**: 2 M points additive ~2-3 ms `[design]`. P2 because the look is dense/thin; works as a background layer.

### G05 L-system trees and plants (growth animation) - P2, L
- **Look**: fractal trees, ferns, Koch/Hilbert/dragon curves, Gosper, Sierpinski arrowhead; growing in time; teamLab-like garden growth (E4).
- **Technique** `[mem]`: string rewriting by rules (F -> FF+[+F-F-F]-[-F+F+F] etc.), then a turtle interprets the string into segments (angle, length decay, width decay).
- **TD build** `[design]`: rewriting + turtle in Python on a `Script`/Table DAT, **cached**, recomputed only on a rule/iteration change (CPU 1-5 ms for ≤200k segments, not per frame); segments written to a texture/POP table and drawn as instanced lines via Geometry COMP (or a Line POP if present in 31550, check dump). Growth = a `Progress` par clips segments by depth/order; wind sway = noise offset by depth in the vertex stage.
- **Pars**: Preset/rules DAT (editable), Iterations 1-8, Angle, Length decay, Width decay, Progress, Sway, Leaf marker (circle/petal sprite), Seed (stochastic rules), Colour by depth/age.
- **Presets**: Binary tree, Fern, Koch snowflake, Hilbert, Dragon, Sierpinski, Plant (stochastic).
- **Not possible in-frame**: re-expanding 8+ iterations per frame on CPU. Mitigation: bake the segment buffer, animate on GPU. **Perf** draw ~0.5-1 ms for 100k segments `[design]`. Difficulty L because of the editor DAT and the instancing bridge.

### G38 Harmonograph / Lissajous / spirograph / rose curves - P2, S
- **Look**: precise looping line figures (spirograph, Lissajous knots, epicycloids, phyllotaxis Vogel spiral).
- **Technique** `[mem]`: parametric curve points via Script CHOP/GLSL POP, glow line draw; damping gives harmonograph decay. Vogel: p_n = sqrt(n) * (cos(n*137.508 deg), sin(...)).
- **TD build** `[design]`: CHOP-generated curve (Pattern/Math/LFO) -> Geometry line or GLSL POP; soft glow via Blur + Add. Phyllotaxis = POP Grid positions remapped in one GLSL POP, sized by distance/audio.
- **Pars**: freq ratios a,b,c 1-16 (integer lock for closed curves), phase drift, damping 0-1, points 1k-100k, thickness, glow, Vogel angle (137.5 default, offset ±1 deg for pattern change), dot radius law.
- **Perf**: <0.5 ms. Pairs with G19 (oscilloscope audio-fed version).

## 3. Group B. Tiles, automata, growth

### G06 Truchet family - P1, S
- **Look**: endless woven arcs/diagonals/mazes; multi-scale Truchet (nested scales) gives organic emergent shapes. Carlson, "Multi-Scale Truchet Patterns" (Bridges 2018): Smith's variant gives continuous lines delimiting two-colourable regions; extended to sets scaled by powers of 1/2 with "winged" tiles `[src]`.
- **Technique**: hash cell -> choose tile orientation; Smith quarter-arc tiles pair two arcs per cell; multi-scale: subdivide cells recursively at probability p with orientation chosen from the allowed tile set at each level `[src: summary, not the paper body]`.
- **TD build** `[design]`: single-pass GLSL TOP (no state), cell hash from Seed + time quantised for stepped animation; anti-aliased arc distance; fill or stroke; per-tile colour from palette by hash/level.
- **Pars**: Tile type (quarter-arc, diagonal, Smith, hex, triangular, 3-scale Carlson), Cell size 8-400 px, Levels 1-4, Subdivide p, Line width, Fill mode (lines/regions two-colour/ hatch), Animation (flip rate, rotate tiles, domain scroll), Seed, Palette by level.
- **Presets**: Weave, Maze, Bridges (multi-scale), Hex knots, Quilt. **Perf**: ~0.3 ms. **Inputs**: image luma modulates cell size (halftone-like Truchet portrait), audio flips tiles on beat.

### G07 Aperiodic and symmetric tilings (Penrose-like, quasicrystal, wallpaper groups, Islamic star) - P2, M
- **Look**: gold-and-geometry patterns; quasicrystal = sum of N plane waves at 2pi/N angles (N=5,7 gives non-repeating look).
- **Technique** `[mem]`: quasicrystal I(p) = sum_k cos(k_i · p + phase_i); wallpaper groups = fold p into a fundamental domain (p4m, p6m, p3m1) then sample a motif; Islamic star = polygon-in-polygon construction via fold + line distance.
- **TD build** `[design]`: single-pass GLSL TOP with a `Mode` menu; the fold library is shared with G16.
- **Pars**: N waves 3-13, Scale, Rotate speed, Phase drift, Wallpaper group (17 menu), Motif source TOP, Line width, Palette. **Perf**: ~0.3 ms. Safe par limits contrast when N high and scale small.

### G08 Cellular automata lab (Life, HighLife, Seeds, Brian's Brain, Generations, Wireworld, cyclic, Larger-than-Life, SmoothLife, Lenia) - P1, M
- **Look**: gliders and blooms (Life), tail-fading Brian's Brain, electrons in circuits (Wireworld: states empty/conductor/head/tail, conductor becomes head with 1 or 2 head neighbours `[src]`), rotating spirals (cyclic), organic creatures (Lenia, `O` rank 6).
- **Technique**: ping-pong state texture; each step reads Moore/von Neumann/radius-R neighbourhood; a GPU Wireworld exists using exactly this fragment-ping-pong scheme `[src hexaflex/wireworld-gpu]`; the naive Life shader reads 8 neighbours `[src gamedev.net]`.
- **TD build** `[design]`: one GLSL TOP in compute mode per step, `npasses` = steps per frame (1-8), state in R32F/RGBA8; display pass maps states to palette, with optional "age glow" (fade of dying cells) and 3-frame bloom. Rule table as a 2x18 lookup DAT -> uniform array for life-like `Bx/Sy` rules (B3/S23, B36/S23, B2/S, ...). Seeding: noise density, random blob, **image-threshold seed (logo/text/face mask)**, drawing via effector Nulls, "glider gun" stamps. Wireworld input: draw circuits from a TOP; it is an authored look, not random.
- **Pars**: Rule (menu + custom B/S), Grid size 128-1080x1920 (cell = 1-8 px), Steps/frame, Wrap, Neighbourhood radius (LtL 1-10), Kernel (SmoothLife ring), Age-glow decay, Colour mode (state/age/neighbour count), Seed pulse, Mutate chance (random flips per frame to avoid extinction), Auto-reseed on dead/stable (hash of state compared to previous, an end-detect pass).
- **Presets**: Classic Life, Gliders, Brian's, Coral (B3/S45678), Cyclic spirals, Wireworld clock, Lenia orbium (if built).
- **Perf** `[design]`: radius-1 rules at 1080x1920 (1 px cell) ~0.4 ms per step; LtL r=7 ~2 ms (225 taps; use 2-pass separable approximation for box kernels); SmoothLife by direct ring sum ~3 ms at 540x960 then upscale.
- **Flash safe**: cyclic CA bands and Life at 1-px cells strobe visually; default cell ≥ 4 px, Safe = limit alive-fraction change per frame.

### G09 Laplacian growth: DLA, dielectric breakdown (lightning), differential growth, coral - P2, L
- **Look**: crystal/frost fractals (DLA), lightning/Lichtenberg trees (DBM), frilly coral lines (differential growth).
- **Technique**: particle DLA is serial-ish (random walkers stick to a cluster, Witten and Sander 1981 `[src]`); a GPU port based on per-particle neighbour search is slow at scale `[src fuseworks]`. **GPU-friendly alternative** `[mem + design]`: solve the Laplace field around the cluster with Jacobi iterations (compute, ping-pong), then each frame grow cells on the frontier with probability proportional to field^eta (dielectric breakdown model; eta=1 gives DLA-like statistics). Differential growth: a polyline with edge-split, repulsion between near points and smoothing; use Neighbor POP `[O F4]` for repulsion (Neighbor POP in a loop = unproven), or CPU Python for ≤20k points.
- **TD build** `[design]`: compute pass A Jacobi (8-32 iterations/frame at 540x960 = low res; field is smooth), pass B stochastic growth at full res, pass C render (age colour, glow). A reset/regrow cycle is mandatory (slow growth saturates).
- **Pars**: eta 0.5-3 (branching), Growth rate, Jacobi iterations, Seed shape (point, line, logo mask, ring), Regrow period 20-600 s, Age palette, Glow, Differential: split distance, repulsion radius, noise.
- **Presets**: Frost, Lightning, Coral, Logo crystallise. **Perf** `[design]`: 2 ms at half-res field. No TD precedent found (O also flags none), so difficulty L, priority 2.

### G37 Recursive split / subdivision (Max Cooper "Parting Ways" look) - see E7.

## 4. Group C. Cells, blobs, SDF, fractals

### G10 Voronoi / Delaunay / Worley toolkit (Jump Flood based) - P1, M
- **Look**: cracked-glass cells, organic cell maps, crackle edges, stained glass, low-poly mosaic, circuit-like Delaunay meshes.
- **Technique** `[mem]`: (a) analytic Worley noise (3x3 neighbour hash) - single pass, up to ~100 animated cells; (b) **Jump Flood Algorithm**: seed texture -> log2(N) passes at step 2^k, each pixel keeps the nearest seed id; gives exact Voronoi for any number of seeds (thousands) or from image edges; (c) Delaunay as the dual: for edge pixels draw lines between the seed pairs found at region boundaries. Distance maps give F1, F2-F1 (edges), cell id, cell centre.
- **TD build** `[design]`: JFA = ~11 compute passes for 1080x1920 (chain of GLSL TOPs mode compute, T-47), seeds from a POP/CHOP -> Render TOP point sprite (1 px id texture). Cell shading pass: flat colour from the underlying video sampled at the seed (stained glass), edges, gradient, bevel.
- **Pars**: Seed count 8-4096, Seed source (random, noise-density, image-luma-weighted, CHOP positions, particles), Motion (drift, flock-lite, audio jitter), Mode (Worley F1/F2/F2-F1/ cell id / flat video sample / low-poly / cracks), Edge width, Edge glow, Relax steps (Lloyd 0-4 for even cells), Palette.
- **Presets**: Stained glass, Cracked, Low-poly portrait, Honeycomb-ish (Lloyd), Cell membrane. **Perf** `[design]`: JFA 11 passes ~1.5 ms; analytic Worley 0.4 ms.
- **Reuse**: shatter and slice FX from td-port use Voronoi-like cuts; this becomes a shared tool.

### G11 Low-poly triangulation of live video - P2, M
- Delaunay-style mosaic by JFA cells with seeds on edges (Sobel/luma-weighted rejection sampling in a compute pass), flat mean colour per cell via a 2-pass accumulate (no atomics: sample the cell centre plus 4 offsets instead of an exact mean). Pars: density, edge bias, jitter, outline, depth-of-flip animation. Perf ~2 ms. Mac note: dedupe with G10 (same engine, new shading).

### G12 Metaball / blob field (2D and 2.5D) - P1, S
- **Look**: gooey merging blobs; Zach Lieberman's "blobs" daily sketches / "Atlas of Blobs" exhibit at M+ `[src: existence of the theme only]`; lava lamp; liquid mercury; neon outlined blobs with hatch fill.
- **Technique** `[mem]`: field f(p) = sum r_i^2 / |p - c_i|^2 (or smooth-min of circle SDFs, IQ smin `[src articles list]`); threshold gives the surface; gradient gives normals for a glossy/“mercury” shade; iso-lines give outlines.
- **TD build** `[design]`: single-pass GLSL TOP, circles from a 64-256 row texture (RGBA32F: x,y,r,id) fed from a CHOP/POP/Table; the same buffer comes from a physics POP (attract/repel/spring). Loop over N per pixel: 128 blobs x 2 MP ~0.8-1.5 ms; tile culling pass if N>256.
- **Pars**: Blob count, Radius law, Merge softness (smin k 0-1), Threshold, Style (flat, mercury, glass/refraction of Input TOP, neon outline, hatch fill, contour bands), Motion (noise wander, springs, audio pulse radius, effector attraction), Edge width, Palette per blob.
- **Presets**: Lava, Mercury, Neon outline, Hatch, Cells (outlined). **Inputs**: face/hand landmarks as blob centres (FT_face_track), audio bands -> radius per blob.

### G13 SDF raymarch scene toolkit (modular, preset scenes) - P1, L
- **Look**: abstract 3D worlds: infinite box tunnels, gyroids, Menger sponges, Apollonian gaskets, blob clusters, glossy chrome, volumetric glow.
- **Technique**: sphere tracing against exact/bound SDFs; operators: smooth union, repetition (domain repetition), twist, bend, fold (IQ's catalogue of primitives/operators/distortions, each labelled exact or bound `[src]`; code snippets MIT, art not `[src quoted in L]`). Add AO by SDF taps, soft shadows, fog, cheap glow = accumulate 1/d along the ray.
- **TD build** `[design]`: single-pass GLSL TOP (raymarch has no inter-pass dependencies, so pixel mode is fine, T-46 not an issue) with `#include`-style code assembled from DAT snippets (primitive library DAT, operator DAT, scene DAT), recompiled only on scene change. `Quality` renders at 1080x1920 x 0.5 then upscales; steps 24-128; early-out.
- **Pars**: Scene (menu), Camera (orbit/fly path/audio-driven), FOV, Steps, Epsilon, Repeat cell, Smooth k, Twist amount, Fold iterations, Light dir/colour, Material (matte/chrome/emissive/toon), Fog, Glow, Palette by iteration count/normal/position, Resolution scale.
- **Presets**: Box tunnel, Gyroid cave, Sponge, Apollonian, Blob orbit, Neon grid. **Perf** `[design]`: 64 steps at half res 0.8-2 ms for simple scenes; fractals (G14) 3-8 ms, so need Quality 0.35 + baked option. **Not possible**: hardware ray tracing. Difficulty L only for the snippet-assembler and the preset set.

### G14 Fractal explorer (Mandelbulb, Mandelbox, Julia 3D, Kleinian, 2D Julia/Mandelbrot/Burning Ship/Newton, orbit traps) - P2, L
- **Look**: alien architecture (Mandelbulb), Julia filigree, deep-zoom spirals.
- **Technique**: Mandelbulb power-n map v^n = r^n <sin(nθ)cos(nφ), sin(nθ)sin(nφ), cos(nθ)>, orbit v -> v^n + c, typical n = 8, found by Daniel White and Paul Nylander in 2009 `[src Wikipedia]`; distance estimate DE = 0.5 ln(r) r / dr with running derivative dr `[mem]` (Wikipedia does not give it). Mandelbox = box fold + sphere fold + scale `[mem]`. 2D deep zoom needs more than float32 precision beyond ~1e5 zoom: **two-float (double-float) arithmetic** emulation, or perturbation theory with a CPU reference orbit `[mem]`; Mac has no doubles.
- **TD build** `[design]`: G13 raymarcher with fractal DE modules; 2D fractals as single pass with `Iterations` 32-512 and smooth colouring; deep zoom = reference orbit in Python (mpmath if present, check) uploaded as a 1xN texture.
- **Pars**: Fractal (menu), Power 2-16 (animate for morph), Iterations 4-16 (3D), Bailout, Julia c (animate on a circle or audio), Fold params, Zoom, Centre, Orbit-trap shape (point/line/circle -> colour), Palette by trap/angle.
- **Perf**: 3D Mandelbulb DE at half-res 4-8 ms `[design]` - over budget, so ship with a baked-loop mode (record_chop/Movie Out) and a low-res live mode. Priority 2 for that reason.
- **Licence**: maths is public; many Shadertoy Mandelbulbs are CC BY-NC-SA, do not copy.

### G15 Fractal flame / IFS (Electric Sheep look) - P2, M
- **Look**: glowing swirling flame fractals with log-density tonemapping.
- **Technique** `[mem]`: chaos game: pick a random affine+variation transform (sinusoidal, spherical, swirl, horseshoe, julia...), apply with a colour index blend, plot after 20 warm-up steps, accumulate, tonemap log(density). Original: Draves and Reckase (published algorithm; Electric Sheep itself is GPL, do not copy code).
- **TD build** `[design]`: same as G04: per-frame iterated point state (POP/state texture), additive Render TOP, compute log/gamma/vibrancy tonemap; 3-6 transforms stored in a Table DAT, morph between table rows by a `Blend` par for animation.
- **Pars**: Transform table, Variations (per transform, weights), Points 0.5-4 M, Exposure, Gamma, Vibrancy, Symmetry (rotational 1-8), Palette, Morph speed. **Perf**: ~2-3 ms `[design]`.

### G28 Domain-warp ink / marble (IQ-style warped fbm) - P1, S
- **Look**: marbled paper, smoky ink, oil slick; f(p + fbm(p + fbm(p))) `[mem]`.
- **TD build** `[design]`: single-pass GLSL TOP, 2-3 nested fbm (4-5 octaves): ~0.8 ms. Pars: warp depth 1-3, warp amount, scale, octaves, drift, Palette by value and by gradient magnitude, relief shading (emboss). Presets: Marble, Smoke, Oil, Lava. Overlaps `ink_flow`/`B_visual_techniques`; keep one shared module.

### G29 Gyroid / TPMS / isosurface slice shader - P3, S
- Cheap 2D slices of triply periodic minimal surfaces (gyroid sin x cos y + sin y cos z + sin z cos x) with animated slice plane, shown as contour lines; the raymarch version is a G13 preset. Pars: scale, slice speed, thickness, contour count. ~0.3 ms.

## 5. Group D. Mirror, op-art, data-viz

### G16 Hyperbolic and Droste tilings, extended kaleidoscope - P2, M
- **Exists (td-port)**: `kaleido` (mirror folds), `tunnel`, `tile`, `ripple`. **Add** `[mem]`: Poincare-disc {p,q} tilings (inversion in circles = fold group; Escher "Circle Limit" look), Droste (log-polar zoom + spiral map: image contains itself), mirrored-fold Kleinian, per-fold rotation noise, kaleido of a live camera ROI, infinite-zoom feedback tunnel.
- **TD build** `[design]`: single-pass GLSL, iterated folds (≤24); log-polar map p -> (ln r, θ) then rotate-and-scale modulo; sampling uses mip/anisotropic LOD to avoid shimmering at the centre (set `Input Extend: Mirror`).
- **Pars**: p,q (3-12, with hyperbolicity check (p-2)(q-2) > 4), Fold count, Rotate speed, Droste scale/twist, Zoom speed, Centre (effector/face), Mirror mode, Edge glow. **Perf**: 0.3-0.6 ms. **Extension of td-port rather than a new base**.

### G17 Op-art and moire - P1, S
- **Look**: Bridget Riley waves and Vasarely grids, line-grating moire, concentric circle moire, bulging grids, checkerboard warps. `[mem]`
- **Technique**: two (or more) slightly different periodic gratings overlaid => beat patterns; drive via small rotation/scale/phase differences; Vasarely bulge = grid coordinates passed through a lens map; Riley waves = sinusoidal displacement of stripe phase with varying frequency.
- **TD build** `[design]`: single-pass GLSL; layers 1-4 each with type (lines, circles, dots, checker, radial rays), frequency, angle, phase, duty cycle, warp; combine by multiply/XOR/difference. Moire is resolution sensitive: render at 2x supersample or analytically antialias the gratings (use fwidth-equivalent step).
- **Pars**: Layer count, per-layer type/freq 2-400 lines/screen/angle/phase speed/warp (noise amount, sine waves, lens centre+strength), Combine mode, Contrast, Colour A/B (palette), Safe.
- **Presets**: Riley waves, Vasarely sphere, Circle moire, Line pair, Dots. **Perf** ~0.4 ms. **Flash safe (important)**: high-contrast fine gratings are a known photosensitivity trigger; `Safe` limits spatial frequency x contrast and phase speed; default off-white/charcoal, not pure B/W.

### G18 Ridgeline / "Unknown Pleasures" - P1, S
- **Look**: stacked waveform lines with hidden-line occlusion (the Joy Division sleeve style, a data-viz classic).
- **Technique** `[mem]`: N rows of history; each row displaced by amplitude from the audio spectrum (or a CHOP), drawn as a filled polygon in the background colour front-to-back to occlude lines behind.
- **TD build** `[design]`: Audio Spectrum CHOP -> history via Shuffle/Trail CHOP -> Geometry instanced lines + black fill (painter's algorithm in Render TOP with depth), or pure GLSL TOP: per pixel, test the row's height function. ~0.5 ms.
- **Pars**: Rows 20-120, Width, Bin smoothing, Amplitude, Perspective tilt, Line width, Fill, Scroll speed, Colour (white on black / palette per row / gradient), Lowest/highest bin. **Inputs**: audio, any CHOP, image luma scanlines (scanned image as terrain).

### G19 XY oscilloscope vector look (Jerobeam Fenderson style) with phosphor persistence - P1, M
- **Look**: glowing vector lines drawn by the audio's L/R channels as X/Y; green/white phosphor trails, "Oscilloscope Music" shapes; also CRT vector games.
- **Technique** `[mem]`: audio frame at 44.1/48 kHz plotted as connected points (X = L, Y = R); brightness inversely proportional to beam speed (slow beam = brighter dot); phosphor decay in a feedback buffer; bloom.
- **TD build** `[design]`: Audio Device In/File CHOP -> CHOP to POP/Geometry as a line strip (1-2k points per frame) -> Render TOP additive with gaussian-profile line sprite; brightness-by-speed in a GLSL POP. Persistence = Feedback TOP * decay; glow = 3-level Blur add. Synthetic mode: draw shapes by CHOP functions (G38) without audio, or text/logo path -> beam path (reuse `LP_laser_path`'s optimised path = same job, drawn in screen space).
- **Pars**: Gain X/Y, Rotation, Samples per frame, Beam width, Intensity law, Persistence 0-0.99, Glow, Colour (P1 green, P31 blue-white, palette), Grid graticule on/off, Beam-off blanking. **Perf** ~1 ms. **Mac**: macOS Line width MAT par does nothing (O s1), so lines are sprites/quads (POP `Line`/`Trail` or Geometry ribbon).

### G20 Data barcode / test-pattern (Ryoji Ikeda look) - P1, M
- **Look**: black/white barcodes, binary grids, ultrafast pixel-scanning bars, numeric readouts; Ikeda's *test pattern* converts "any kind of data (text, sounds, photos, movies)" into barcode and binary 0/1 patterns in real time (credit: concept Ikeda, programming Tomonaga Tokuyama; 8 barcode channels tightly synchronised; velocity of hundreds of frames per second at points) `[src ycam]`. What *data-verse* does technically is **not documented in the results** `[src gap]`.
- **Technique** `[design from the description]`: read a data stream (audio waveform window, image row, text bytes) -> threshold/quantise to 1 bit -> draw as vertical bars of width proportional to sample run length (run-length barcode) or as bit grids; stack channels as horizontal bands; the strobing look comes from updating at display rate with alternating polarity.
- **TD build** `[design]`: CHOP -> Script/GLSL texture 1xN (bits) -> single-pass GLSL TOP draws bands: modes (run-length bars, bit matrix, byte columns, hex digits via Text TOP atlas or SDF digit font, scanline of an image via threshold). Optional `Quant`: 1-bit / 2-bit / 4-bit greys.
- **Pars**: Channels 1-16, Mode, Source (audio L/R, FFT, image row scan, text/bytes DAT, counter), Bar min width 1-16 px, Update rate (hold N frames), Polarity flip, Threshold, Glyph size, Grid lines, Inversion on kick, **Safe flicker cap** (max 3 flashes/s by default, user may override only in a rehearsal mode; hundreds of fps black/white flicker, as in the original, is a photosensitivity hazard).
- **Presets**: Barcode wall, Bit grid, Hex readout, Waveform scan, Binary rain. **Perf** ~0.3 ms.

### G21 Glyph rain / terminal data wall - P3, S
- Matrix-style falling glyphs, hex dumps, log tickers (Text TOP atlas + instanced quads or compute-drawn from a glyph atlas texture). Overlaps `ascii` in td-port and `lyrics_feed`; ship as a mode of G20 rather than separate. Pars: columns, fall speed, trail, charset (hex/binary/Urdu digits/custom), highlight head. ~0.4 ms.

### G22 Network / constellation graph (force-directed) - P2, M
- Nodes + edges laid out by a force simulation (repulsion all pairs via Neighbor POP or grid hash, springs on edges), edges drawn as lines with distance fade, node glow. Source graph: random geometric, k-nearest, a table of links (people/songs), or tracked points. StageLab has a `Constellation` plugin pending port (INVENTORY); this is the TD module. Pars: nodes 20-5000, link radius, spring k, repulsion, damping, node size by degree, edge fade. 1k nodes + knn ~1.5 ms `[design]`; Neighbor POP in a loop is unproven (O F4, F11).

### G23 Spectrogram waterfall / radial spectrum / waveform tunnels - P2, S
- Scrolling spectrogram (texture row append, `Feedback` with offset), radial spectrum rose (polar remap), waveform tunnel. Most already inside `LK_spectrum_glass`; list as extension modes. Pars: scroll direction, scale (log/mel), palette, peak hold, mirror. ~0.3 ms.

### G24 Contour / isoline topographic lines - P2, S
- Isolines of any scalar field (noise, depth cam, luma, fluid pressure): `abs(fract(v*N)-0.5)/fwidth(v)` band lines, with elevation tint; "topo map" look on the live camera or depth. Pars: count, line width, min/max band emphasis (every 5th thick), fill, animation (field offset), field source. ~0.3 ms. Reuse DC_depth_cam. StageLab has `Contour` pending port.

### G25 Halftone, dither, stipple art (existing: `halftone`) - P3, S
- Extension only: Floyd-Steinberg is serial, so use blue-noise or Bayer ordered dither in a single pass (TD has no serial scan), weighted stippling via JFA/Lloyd (G10) for the stipple-portrait look. Pars: dot shape, angle per CMYK channel, size, ink colours, paper colour.

### G26 Lenia / continuous CA - see G08 (kernel mode) - P2.

### G27 Cymatics / Chladni plate - see O rank 7 (P2); extension: nodal lines of cos(nπx)cos(mπy) - cos(mπx)cos(nπy) = 0 `[mem]`, particles settle on zeros (sand) by gradient-descent compute. S-M.

## 6. Group E. Artist and studio looks (technique emulation only)

Shared rule: reproduce the **method and visual grammar**, never frames, logos or character assets; each emulation gets a neutral name (no artist name in user-facing pars), and a one-line credit in the build doc. What the searches did and did not give is stated per artist.

### E1 / G31 "Data pigment" painting (Refik Anadol look) - P2, L
- **Sources `[src]`**: Anadol's studio trains StyleGAN/StyleGAN2/ADA on huge photo sets (e.g. "over 100 million images" for Urban Dreams; 9.5 M after removing people for the NYC work), with 1024-dim embeddings, a custom "Latent Space Browser" for curated latent walks, and **fluid-solver particle "data pigments"** (MoMA Fluid Dreams: ~100 million particles, pre-rendered, not real time; GPU fluid solvers and ray-traced lighting) `[src nvidia artists page + press]`. Whether Unreal is used is **not in the sources** `[src gap]`.
- **Real-time emulation** `[design]`: you cannot run StyleGAN at show rate here; what reads as "Anadol" is (1) a **dataset mosaic** of many images that morph, (2) **colour-sampled luminous particles** advected by a **fluid/curl velocity field**, (3) slow camera drift, depth-of-field glow, (4) a black void with ribbon-like flows.
- **TD build**: `BO_particles` (instance count 1-2 M) with per-particle colour fetched from an image atlas TOP (the "dataset": N PRISM stills tiled in a 8x8 atlas; per-particle atlas index changes over time); velocity = fluid2d velocity + G01 curl; "latent morph" faked by crossfading atlas index while particles keep position (they carry the colour change); optional ComfyUI (AL) to generate image-set variations offline. Bokeh DOF and fray from `BR` (Ruben Fro looks) reused.
- **Pars**: Atlas source (folder), Particle count, Flow scale/strength, Fluid coupling, Colour sampling mode (position-lookup, id-lookup, vortices-by-hue), Morph rate, Depth blur, Glow, Palette lock (limit to PRISM palette).
- **Perf**: 1 M particles + fluid2d ~6 ms `[design]` -> over budget on its own; ship as `Quality` (500k + half-res fluid) and a recorded pre-render loop for the heavy version. Also say honestly: the "AI" part is offline here.

### E2 / G32 Ikeda data look - see G20 (P1).

### E3 / G33 Line-volume projection light sculpture (Joanie Lemercier look) - P2, M
- **Sources `[src]`**: Lemercier projects onto room surfaces and 3D volumes/polygonal sculptures with a second "light sculpture" layer; a wireframe scene revealed through soft light painted on a wall (Eyjafjallajokull); paper-folded pyramids lit with projections; left AntiVJ in 2014 for own studio. I found **nothing on "Eclipse"/"Hypercube" specifics** `[src gap]`.
- **Look grammar** `[design]`: monochrome/limited palette hairlines, hatching and wireframe rasterised as light, parallax-correct on planes (needs the previz/projection mapping), moire from slightly offset line sets (G17), geometric solids rotating.
- **TD build**: (a) wireframe renderer: Geometry COMP of primitive solids (Sphere/Box/Torus/Icosphere) with Wireframe MAT or edge-detect on normal/depth buffer (macOS line width ignored, so use screen-space edge detection on a normal TOP + 1-2 px AA), (b) hatching: world-space stripe function modulated by light angle (tonal art map), (c) "relief grid": grid of lines vertically displaced by a height TOP seen in perspective (Joy Division 3D), (d) soft reveal masks via G28 noise thresholds. Projection correctness comes from `PV_previz_stage`/`LK_projection_room`.
- **Pars**: Solid (menu), Wire thickness, Hatch density/angle, Depth fade, Reveal threshold, Rotation (audio), Line colour, Plane tilt.
- **Perf** ~1 ms. Presets: Wire solids, Hatch sphere, Relief grid, Moire planes.

### E4 / G34 Flowers/waterfall/calligraphy (teamLab look) - P1, L
- **Sources `[src]`**: *Flowers and People, Cannot be Controlled but Live Together, for Eternity*: rendered continuously in real time by a program (not a loop); sensors detect visitors; flowers bloom more when a viewer stands still and scatter when they move or touch the wall; a year of flower growth compressed to about an hour; states never repeat. No engine/code is published `[src gap]`.
- **Emulation** `[design]`: (1) **Flower life cycle**: instanced procedural flowers (petal ring = 5-9 curved quads/SDF-sprite in a GLSL POP), each with a birth time, bloom curve (smoothstep radius growth), hold, wilt (colour desaturate, petals detach and fall), death; spawn density controlled by `Stillness` (person mask area motion low => bloom, high => scatter); (2) **Waterfall**: columns of falling particles/lines from the top (vertical 1080x1920 fits), with collision against obstacle mask (person mask, depth cam) so water parts around people, mist at the bottom; (3) **Ink calligraphy**: brush strokes as ribbons along curl paths with width by speed, ink fading.
- **TD build**: BO_particles (instance petals from a quad sprite atlas of ~8 flower SDF shapes), a life-cycle state texture (age, seed, species), mask from `person_mask`/`DC_depth_cam` as the stillness source (frame difference energy: no optical flow needed), colour palette by species.
- **Pars**: Species mix, Bloom time 5-120 s, Density, Stillness gain, Scatter strength, Wind, Fall speed (waterfall), Obstacle mask source, Ink width/fade, Palette (limited 6-colour), Season clock speed (day-length compression).
- **Perf**: 100k flower instances (petals batched) ~2-3 ms `[design]`. Priority 1: strongest fit for the vertical wall and audience interaction (`M_audience_interaction.md`).

### E5 / G35 Light-column and LED-array fields (UVA / Volume look) - P2, M
- **Sources `[src]`**: UVA's *Volume* is a field of light-and-sound columns (47-48 columns) reacting to visitors, V&A commission, D&AD Yellow Pencil 2007; the 2006 Massive Attack tour used 240 Chroma-Q Color Block LED fixtures forming a curved audio-responsive screen with real-time information; *Speed of Light* used 148 lasers and optical fibre; UVA's proprietary simulation "D3" (later disguise) `[src wikipedia/disguise/vjstv summary]`. How they generated the content is **not detailed** `[src gap]`.
- **Emulation** `[design]`: low-resolution pixel-grid look: a coarse grid (e.g. 24x96 "fixtures") sampled from any source with a hard LED bloom, columns with heights/brightness driven by audio or person proximity, text/data overlays at LED resolution, beam arrays (vertical beams with haze falloff).
- **TD build**: Input TOP -> Resolution (coarse) -> nearest-neighbour upscale with circular LED mask + bloom (single GLSL pass); column field = grid of vertical line segments from a CHOP of N values (heights), beam falloff `exp(-|x-xi|*k)`, optional haze 1D noise. Ties to `LP_laser_path`, `BK_dmx_out` (pixel mapping out to real fixtures).
- **Pars**: Grid W/H, Fixture shape (round/square/line), Bloom, Gamma (LED response), Height source (audio bands, proximity, pattern), Beam length/haze, Scan speed, Text/data mode. ~0.4 ms.

### E6 / G36 Moment Factory / Tundra - **not researched to a technique** `[src gap]`
- The searches returned nothing connecting either studio to a documented technique (the one search that included them returned only UVA material). I make no claim about them. Their public work is mapping/interactive spaces generally, which this file already covers by G13, E4, E5, E7. Left as an open item (section 8).

### E7 / G30 Recursive split and "grid-snapped hits" (Max Cooper videos) - P1, S-M
- **Sources `[src]`**: Maxime Causeret's *Parting Ways*: "started from a very simple element, a box, and made it split again and again", built in Houdini; Maxime Teresuac's *Order from Chaos* (Houdini): colourful dynamic visuals on black, brief based on rain-hit binaural recordings **forced toward a grid so a pattern emerges**; Nick Cobby's *Everything* = animated photo-collage `[src lesterbanks/dezeen/cdm summary]`.
- **Emulation** `[design]`: (1) **Recursive split**: BSP subdivision of the frame (or a 3D box) driven by a split-event clock: each beat picks a leaf (random or largest) and splits at 30-70 %; leaves get colour/gap/inset; animate the split as a sliding seam (ease); seen as flat 2D rects (Mondrian-ish) or extruded 3D boxes; data in a Table DAT (leaf rows) rendered by a single GLSL pass up to 512 leaves or by instanced boxes; (2) **Order from chaos**: random impacts (circle ripples) whose positions are blended toward a lattice by `Order` 0-1; ripples cast as expanding rings with interference; at Order=1 a perfect grid emerges; (3) **Photo collage**: tile/slice (td-port `slice_tile`, `slice_tiler`).
- **Pars**: Split rate (beat sync), Split ratio range, Max leaves 16-512, Gap, Inset, Colour per leaf (palette/random/depth), Extrude (0 = 2D), Shape (rect/rounded/circle-in-rect), Order 0-1, Lattice pitch, Ripple speed/decay, Seed.
- **Perf** ~0.4 ms 2D; 3D instanced 512 boxes ~1 ms.

### E8 / G34b Ribbon brush / gesture lines (Zach Lieberman look) - P1, M
- **Sources `[src]`**: daily "sketches" since 2016 (15 s - 1 min screen recordings), mostly openFrameworks (which he co-created), playful systems, vibrant palettes, blobs (G12). Specific technique breakdowns were **not returned** `[src gap]`; the following is the visual grammar, not his code.
- **Emulation** `[design]`: (a) **Ribbon brush**: polyline trails from hands/face landmarks (FT_face_track) with width by speed, colour by velocity direction, 0.5-3 s fade, smoothed Catmull-Rom; (b) **Noise-displaced lines**: grid of lines displaced by noise/face mesh; (c) **Face/body as SDF**: person mask -> distance transform (JFA) -> contour bands/blobs around the person; (d) **Text as SDF** with outline layers and wobble (Text TOP -> JFA distance -> iso bands).
- **TD build**: Trail POP/Trail SOP for ribbons; instanced quad strip with width channel; distance transform from G10 JFA for (c)/(d).
- **Pars**: Source (hands, face landmark index, mouse, effector Null), Width law, Smooth, Fade, Colour mode, Band count and spacing (SDF), Wobble, Layers.
- **Perf** ~1 ms. Priority 1: reacts to people with no new sensors.

### E9 Mapped-surface "architecture" looks - covered by AB/AT/AW, nothing new here.

### E10 Ruben Fro - already done (BR / PX).

## 7. How to extend what already exists

| Existing | Extension from this file |
|---|---|
| `BO_particles` | Modes: Streamlines (G01), Attractors (G03), Flame (G15), Flowers (E4), Pigment atlas (E1) |
| `BN_fluid2d` | Velocity export to G01/G02/E1; obstacle mask from person for E4 waterfall |
| `FX_palette_map` | Palette par on every effect; ramp by "age/speed/iteration" channels |
| `FX_motion_trail` | Phosphor persistence in G19; trail in G01 |
| `FX_strobe` | `Safe` limiter for G17, G20, G08; shared flash-rate meter |
| `TP_test_pattern` | G20 data barcode as an additional pattern family |
| `FT_face_track`, `DC_depth_cam`, person mask | Inputs for E8, E4, G12 blobs, G10 sampling |
| `LP_laser_path` | G19 draws the same path in screen space; beams (E5) |
| `PV_previz_stage`, `LK_projection_room` | Check E3 on the real planes |
| td-port `kaleido`, `tunnel`, `tile`, `ripple` | G16 (hyperbolic, Droste, fold library) |
| td-port `halftone`, `ascii` | G25 stipple, ordered dither; G21 glyph rain |
| td-port `ink_flow`, `flow_fx`, `shatter`, `slice_*` | G28, G02, G10, E7 |
| `PX_pointfx` | Effectors shared (G01, G03, E4) |

## 8. Ranked backlog (priority, difficulty, perf estimate)

| ID | Effect | P | Diff | est ms `[design]` | Depends on |
|---|---|---|---|---|---|
| G06 | Truchet family | 1 | S | 0.3 | - |
| G17 | Op-art / moire | 1 | S | 0.4 | Safe limiter |
| G18 | Ridgeline | 1 | S | 0.5 | audio |
| G28 | Domain-warp ink | 1 | S | 0.8 | - |
| G12 | Metaball / blob field | 1 | S | 1.0 | face track optional |
| G20 | Data barcode (Ikeda look) | 1 | M | 0.3 | Safe limiter |
| G19 | XY phosphor scope | 1 | M | 1.0 | audio |
| G03 | Attractor dust | 1 | M | 2.0 | POP loop (scratch TD) |
| G08 | CA lab (+Wireworld, Lenia) | 1 | M | 0.4-3 | compute chain |
| G01 | Flow-field streamlines | 1 | M | 1-4 | BO_particles |
| G10 | Voronoi / JFA toolkit | 1 | M | 0.4-1.5 | compute chain |
| E7/G30 | Recursive split / ordered ripples | 1 | S-M | 0.4 | beat clock |
| E8/G34b | Ribbon brush | 1 | M | 1.0 | face track |
| G13 | SDF raymarch toolkit | 1 | L | 0.8-2 | - |
| E4/G34 | Flowers / waterfall / ink | 1 | L | 2-3 | person mask |
| G02 | LIC ink | 2 | M | 1.0 | fluid2d |
| G04 | Clifford / de Jong density | 2 | S-M | 2-3 | additive Render |
| G15 | Fractal flame | 2 | M | 2-3 | additive Render |
| G16 | Hyperbolic / Droste | 2 | M | 0.5 | - |
| G07 | Quasicrystal / wallpaper | 2 | M | 0.3 | - |
| G09 | Laplacian growth / DLA | 2 | L | 2 | compute chain |
| G11 | Low-poly triangulation | 2 | M | 2 | G10 |
| G14 | Fractal explorer | 2 | L | 3-8 | G13, baked loops |
| G05 | L-systems | 2 | L | 0.5-1 | Python cache |
| G22 | Force-directed graph | 2 | M | 1.5 | Neighbor POP (unproven) |
| E3/G33 | Line-volume light sculpture | 2 | M | 1 | previz |
| E5/G35 | Light-column / LED array | 2 | M | 0.4 | - |
| E1/G31 | Data-pigment painting | 2 | L | 6 (heavy) | BO, fluid2d |
| G23 | Spectrogram modes | 2 | S | 0.3 | - |
| G24 | Contour lines | 2 | S | 0.3 | depth cam |
| G27 | Cymatics | 2 | S-M | 1 | - |
| G38 | Harmonograph / phyllotaxis | 2 | S | 0.3 | - |
| G29 | Gyroid slice | 3 | S | 0.3 | - |
| G21 | Glyph rain | 3 | S | 0.4 | mode of G20 |
| G25 | Stipple / dither | 3 | S | 0.5 | G10 |

Build order suggestion (parallel lanes, 2-6 as the live-lane rule allows): lane 1 pixel one-passers (G06, G17, G28, G18, G38, G07, G24), lane 2 compute chains (G08, G10, G02), lane 3 POP/particles (G03, G01, G04/G15 via scratch TD), lane 4 SDF (G13 then G14), lane 5 interactive (E8, E4, G12). Pilot one item first (G06) to fix the module template, then run the rest at once.

## 9. Open items and sources

Open: (1) Moment Factory and Tundra techniques were not found; (2) Ikeda's *data-verse* pipeline is undocumented in the results; (3) whether the Line POP and a Delaunay op exist in 31550 must be checked in `ops/ops_*_2025.31550.json` before G05/G11 (not checked today); (4) Carlson's paper body, Draves' flame paper and the dynamicmath attractor list were not read (only abstracts/links); (5) all perf figures are unmeasured; (6) no live TD verification of any effect here.

Sources used on 26 Oct 2026: [NVIDIA artists page, Anadol](https://images.nvidia.com/artists/refik-anadol/), [Dezeen Anadol/NYC](https://www.dezeen.com/?p=1429098), [YCAM test pattern](https://special.ycam.jp/datamatics/en/testpattern.html), [cdm.link Lemercier light sculptures](https://cdm.link/light-sculptures-making-visuals-literally-3d/), [teamLab Flowers and People Tokyo](https://www.teamlab.art/w/flowerandpeople-tokyo), [Superblue teamLab](https://www.superblue.com/miami/experience-guide/teamlab-between-life-and-non-life), [Derivative strange attractors POPs tutorial 06](https://derivative.ca/community-post/tutorial/touchdesigner-tutorial-06-strange-attractors-pops/72620), [Carlson Multi-Scale Truchet, Bridges 2018](https://archive.bridgesmathart.org/2018/bridges2018-39.html), [UVA, Wikipedia](https://en.wikipedia.org/wiki/United_Visual_Artists), [disguise Volume world tour](https://origin.disguise.one/en/insights/case-studies/volume-world-tour), [Dezeen Order from Chaos](https://www.dezeen.com/?p=1028980), [lesterbanks Parting Ways](https://lesterbanks.com/2019/10/max-cooper-parting-ways-official-video-by-maxime-causeret/), [Lieberman, M+ Atlas of Blobs](https://www.mplus.org.hk/en/exhibitions/zachary-lieberman-atlas-of-blobs/), [Lieberman KIKK](https://2023.kikk.be/kikk-for-pro/conferences/zach-lieberman), [fuseworks DLA](https://fuseworks.it/research/diffusion-limited-aggregation), [wireworld-gpu](https://github.com/hexaflex-zz/wireworld-gpu), [Wikipedia Mandelbulb](https://en.wikipedia.org/wiki/Mandelbulb), [IQ distance functions](https://iquilezles.org/articles/distfunctions), [Codrops RD compute](https://tympanus.net/codrops/2024/05/01/reaction-diffusion-compute-shader-in-webgpu/). Licence rulings: `L_shader_sources_licences.md`. Platform facts: T-18, T-46, T-47, `O_generative_simulations.md`, `E_live_rig.md`.
