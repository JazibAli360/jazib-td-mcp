# FX4 - Software FX emulation: what VJ / motion / VFX tools offer that we can rebuild in TD (26 Oct 2026)

Offline research (TD not touched, nothing downloaded beyond page text). Target: TD 2025.31550, macOS Rosetta, Vulkan/MoltenVK,
1080x1920, 60 fps, ~3 ms per COMP. Rules that shape every recipe below: multi-pass = **compute-mode GLSL TOPs only** (T-46/T-47),
**no Optical Flow TOP** (T-18), no codec motion vectors, GLSL out-of-bounds can crash (T-35), flash limits apply to datamosh /
strobe-like effects (J_interactive_camera_effects §flash rule: >3 flashes/s over >25% of the screen is out).
Perf numbers are **estimates, not measurements** unless a row says "measured" (none here). Priority 1-3 = live-visuals value
(1 = build first). Difficulty S/M/L.

User ask that triggered this wave: "destruction type effects, datamoshing and etc". Section 3 is that part in depth.

## 0. Sources and how reliable each is

| Source | What was read | Reliability |
|---|---|---|
| **Installed Arena 7.23.2 binary** (`/Applications/Resolume Arena/Arena.app`, `strings` read-only; no Arena run, no REST/OSC) | The full list of built-in effect / mixer / generator names with their tooltips (sec 1) | High for names + tooltips; no param ranges. Not an install-provenance check (host-install rule: none done). |
| `/Applications/Resolume Arena/plugins/wire/*.wired`, `default/Presets/Video Effects/` | The 14 Wire-built effects shipped with 7.23 + preset folders | High (file names) |
| [Notch manual 2026.1 node reference](https://manual.notch.one/2026.1/en/docs/reference/nodes/) | Post-FX, Fields, Particles, Deformers lists (sec 2) | High; first 100,000 of 121,681 chars read |
| [Boris FX Sapphire OFX picture index](https://borisfx.com/documentation/sapphire/ofx/picture-index) | Effect names by group (sec 4); Builder/Render/Keying groups not seen (page truncated) | High for names |
| [Maxon Red Giant help index](https://help.maxon.net/rg/en-us/Content/html/Cat_Overview.html) | Universe / Trapcode / Magic Bullet / VFX effect names (sec 4) | High for names; Mir page only gave group titles (Geometry, Repeater, Fractal, Material, Texture, Shader, Visibility, Rendering) |
| [Codrops real-time datamosh (Three.js)](https://tympanus.net/codrops/?p=119915), Modrinth datamosh shader, [Interactive & Immersive HQ datamosh article](https://interactiveimmersive.io/blog/content-inputs/datamoshing-in-touchdesigner/) | Datamosh concepts (sec 3.1). Search snippets only; bodies not opened. | Medium |
| [VIDVOX docs](https://docs.vidvox.net/vdmx_isf.html) | VDMX ships ~200 ISF files; Quartz Composer sunset; Rutt Etra needed a Metal rewrite | Medium (snippet) |
| [Cavalry 2020 overviews](https://evermotion.org/articles/show/11838/cavalry-new-motion-design-tool) | Elements = Shapes, Behaviours (40+), Atoms, Effects; Duplicator + Effectors + Falloffs | Medium (old; check Scene Group docs) |
| [SideFX Houdini docs (Chaos integration)](https://sidefx.com/docs/houdini/unreal/chaosintegration.html) | Voronoi fracture + `unreal_gc_piece` to Unreal Geometry Collections | Medium; RBD / Vellum / POP-grain internals below are from general knowledge, marked (K) |
| Web search did not return Resolume's own effects manual | Replaced by the binary read above | - |

Items marked **(K)** = from the author's general knowledge, not re-verified this session. Licences: none of this research copies
code; maths and look descriptions only. Shadertoy / ISF shaders are named as technique pointers, licence per file (L_shader_sources_licences.md).

## 1. Resolume Arena 7.23.2 - the built-in list, grouped, with TD status

(Names read from the Arena binary. Param names / ranges NOT read; open Arena's Effects panel when a clone must match exactly.
**Every Arena call still needs the user's go-ahead**, none was made.)

Legend for the TD column: **N** native op chain exists in TD (palette / basic TOPs), **L** already in `/project1/lab`,
**P** td-port effect exists (separate project, mostly "offline gate passed, TD runtime not run"), **G** gap -> backlog id.

### 1.1 Colour / tone (all N unless noted)
Add Subtract (N: Level/Math), Bright.Contrast, Exposure, Levels, Vibrance, Hue Rotate, Colorize, Tint, Color Pass (N: HSV key), Recolor "palette remap" (**L** FX_palette_map), Threshold, Posterize (N: Level/Quantize via Math), To Luminosity, Invert RGB, Solid Color, Heat "fakes thermal imaging" (G: **G-HEAT** thermal ramp + luma, S), Alpha Limiter / Premultiply / RGBA Switch / Format Conversion (N + the premultiplied-alpha rule, memory overlay-alpha-premultiplied).

### 1.2 Blur / glow / sharpen
Blur, HV Blur, Radial Blur (N: Blur / Radial Blur via Transform feedback or GLSL), Pixel Blur (N: Cross/Blur), **Bloom** (G: **G-BLOOM** mip-chain bloom with threshold/knee; Notch has Glow/Glow 2/Physical Glow; S), Sharpen, Pixel High Pass (N: Convolve), Dilate / Kuwahara (G: **G-KUWAHARA** Kuwahara + Dilate/Erode/Median bank, M; Notch also has Dilate, Erode, Kuwahara, Median), Drop Shadow (N), Tilt Shift (Wire effect; G small), Vignette (**P**).

### 1.3 Distortion / warp
Distortion, Wave Warp, Ripples (**P** ripple), Fish Eye, Bendoscope "bend over and relax" (G: **G-BEND** polar bend/fold map, S), Twisted "pixel twister", Fragment "radial fragmentation" (G: **G-FRAG** = cracks/shards, see D3), Blow "smear parts of image" (G: **G-SMEAR** luma-driven directional smear, S), Goo "oozing" (G: **G-MELT**, D7), Suckr (G: black-hole suck, S, part of G-BEND), Freeze "freezes part of image" (N: Cache/Hold + mask), Stop Motion (N: Hold TOP + step), Trails (**L** FX_motion_trail), Infinite Zoom (G: **G-INFZOOM**, feedback zoom + crossfade of 2 layers, S), Displace "displaces pixels based on luminance" (N: Displace TOP), UV Map (N: Remap TOP), Triangulate "Sierpinski pixellation" (G: **G-TRI**, S), LoRez / Dot Screen / Raster / Dither (G: halftone/dither bank, see 5.1; **P** halftone, pixel_fx).

### 1.4 Mirror / tile / repeat
Mirror, Mirror Quad, Flip, Kaleidoscope, Polar Kaleidoscope (**P** kaleido; extend: triangle / square / oct / fly's-eye families from Sapphire, **G-KALEIDO2**), Tile, Cube Tiles, VideoWall, Keystone / Keystone Crop / Keystone Mask (N: Corner Pin; mapping in `LK_projection_room`), Crop.

### 1.5 Cloners / particles / 3D-ish
Linear Cloner, Radial Cloner, Grid Cloner (Wire), Particle System (**L** BO_particles), Point Grid "grid of points in 3D" (G: **G-FORM** = Trapcode Form look, M), Terrain (G: **G-TERRAIN**, M), Sphere / Stingy Sphere "spikes based on luminance" (G: luma-displaced sphere, M, with Terrain), Snow, Sparkles (G: **G-SPARKLE**, S, rides on BO_particles), Metaballs, Meta Shape / Meta Image "morphs one shape to another based on luminance", Polkadot, Radar, Reveal, Iterate "iterative composition" (feedback transform; **L** partly via motion_trail; G small), Slice Transform.

### 1.6 Stylise / keying / misc
Edge Detection / Edge Detect (N: Edge), Strobe (**L** FX_strobe), Static, Twitch (**P** glitch), Shift RGB / Delay RGB (**P** rgb_split; Delay RGB = per-channel Cache offsets, N), Shift Glitch (**P** glitch), Stripper, Chroma Key, Auto Mask, Circles / Checkered / Grid / Gradient / Line Scape / Sine Wave / Spiral / Waves / Moving Bar / Stroboscope / Static Generator generators (N: Pattern/Ramp/Noise; **L** TP_test_pattern for the technical ones; G: **G-GEN** generator pack, S each), Text Animator (**L** LK_typecore, urdu_type).

### 1.7 Wire-built effects shipped in 7.23 (`plugins/wire/`)
Abstract Field, Acuarela (watercolour), Bumper, Grid Cloner, LUT (N: Lookup), PiP, SearchLight, Shape Mask, **Slice Delay** (**P**), **Slice Outline** (**P**), Strokes, Tilt Shift, Tunnelines, WarpSpeed. Arena 7.23 also lists third-party / community effects (FeedbackPro, Smooth Transform, Screen Shake, Kaleido FX); StageLab already replaces the useful ones with JZB_* FFGL.

### 1.8 Transition mixers (clip-to-clip)
Push L/R/U/D, Rotate X / Y, Side by Side, Static, Shift RGB, Tile, Twitch, Time switcher, Wipe Ellipse, Zoom In / Out, Soft Light / Screen / Subtract 50 blend modes. Gap: **G-TRANS** a transition bank in the `td_layer_mixer` family (gl-transitions MIT set: 68+ already inside ISF-Files; cube, swirl, glitch, burn, displacement). M, priority 2.

### 1.9 Audio FX (VST bundle)
Bitcrusher, Distortion, EQ-3, Flanger, High/Low-pass. Out of scope for visuals (Ableton / TD audio chain covers it).

**Reading of the Arena list:** ~85 effects, almost all are 1-pass colour/warp filters that TD natives or the td-port covers.
Genuine gaps are the "3D point / mesh" ones (Point Grid, Terrain, Sphere), Bloom/Kuwahara-type image-processing, melt/smear
displacement, and a generator pack. The valuable new work is in sections 3 and 5.

## 2. Notch (2026.1) node reference vs TD

| Notch group | Nodes (verbatim from the manual) | TD today | Gap / how |
|---|---|---|---|
| Post-FX Distortion | Distortion, Dither, Line Distortion, Noise, RGB Distortion | N + P rgb_split | Dither = G-DITHER (5.1) |
| Post-FX Stylisation | Block Glitch, Chroma Glitch, Cross Hatch, Dot Matrix, Film Grading, Halftone, Image Distance, **Motion Datamosh**, Outlines, Physical Lens Flare, **Pixel Sort**, Pixelate, Sharpen, Slit Scan, Streaks, Vector Blur, VHS Scanlines, Voronoi Post Process | P: glitch, halftone, pixel_fx, slit_scan; **G**: datamosh, pixel sort, cross hatch, VHS, lens flare, vector blur (datamosh needs motion; vector blur = flow-based) | D1, D2, 5.1 |
| Post-FX Image Processing | Bit Crush, Channel Boolean, Dilate, Edge Detect, Erode, **Frame Buffer / Frame Delay / Frame Difference / Frame Loop**, Generate Normal Map, Histogram Normalise / Threshold, Kuwahara, Median, Range Remap, Threshold, **Background Plate Subtract**, NVIDIA Virtual Background | N (Cache, Difference, Threshold); person mask **L/in progress** | G-KUWAHARA; Frame* = Cache TOP; "Histogram Normalise" = auto-levels (G-AUTOLEVEL, S) |
| Post-FX Warping | Barrel, Bezier, Bump Map, **Curl Noise Warp**, Droste, Field / Field Position Warp, Four Point, Mirror, **Moebius**, Polar, Radial, **Randomise Tiles**, Ripple, Screen, Sine, Stretch, Transform, Turbulence, Twirl, Water Ripples | Mostly N (Displace + Noise); Droste / Moebius / Randomise Tiles = G | G-WARP bank (S each, one COMP with a mode menu) |
| Post-FX Blur | Directional, Edge-Aware, **Feedback Blur**, FFT Blur / Glow, Frame Feedback, Glow / Glow 2 / Physical Glow, Radial, Tilt Shift, VHS Blur | N / G-BLOOM | |
| Post-FX Colour | Apply LUT, Channel Mixer, Curves, Grading, Limiter, Colour Reduce, Local Contrast, Recolour, Strobe, Tint, Tone Map, Tritone | N + **L** palette_map + strobe | LUT/curves via Lookup TOP |
| Fields | Curl Noise Affector, **Fluid 2D Affector**, Vortex Affector, Mesh Collision Affector, **Reaction-Diffusion**, Field Cloud Material, Field 3D Renderer | **L** fluid2d; RD/physarum in progress | 3D field render = G-VOL (L, low priority) |
| Particles | Flocking, **Fluid SPH / FLIP / MPM** Affectors, Mesh / Spline Emitter, Soft Ball Renderer, Volume Renderer, Voxel Cone Shading, Rigid Body Collision Affector | **L** BO_particles (POP engine + compute fallback) | Flocking (boids, M), SPH/FLIP-lite (L) |
| Deformers | Cloth, Rope, Spline, Bevel, Cut, Extrude Polygons, **Voronoi Fracture**, Slice, Detach Polygons, Noise / Ocean Wave / Sine / Twist / Taper / Bend / Quantise / Sound Deformer, Chunk Effector Deformer, Particle Mesh Deformer, Morph, Face Tracking Deformer, Displacement Map | **L** cloth, pointcloud morph; **P** shatter (2D) | D3 (3D Voronoi fracture + rigid shards), mesh deformer bank (G-DEFORM, M) |
| Physics | Rigid Body, Rigid Body Procedural, Rigid Body Depth Image, Collision Mesh | none | D3 "shard sim", **depth-image collision** (depth cam is L: shards bounce off the performer) |
| Cloners | Grid, Linear, Radial, Random, Spline, Particle, Mesh, Procedural, Paint Clones + FFT Effector | N: Instancing; Arena cloners are G-CLONE | G-CLONE (M, priority 2) |

Notch pattern worth copying: **Fields + Affectors + Effectors share one "field" idea** (a spatial falloff that modulates any
effect). That becomes G-FIELD (sec 5.2), the highest-leverage framework item in this file.

## 3. Destruction and datamosh - the user's explicit ask (cards)

Common rules for D1-D9: COMP name prefix `DX_`; pars via the zkit controls kit; `Amount` 0 = exact passthrough; every card has
`Trigger` (pulse), `Beat` input, `Audio Level` input, and an `Effector` input (Null with a gizmo, per px_requirements.md);
Mac GLSL = compute mode; a fail-safe Switch and a rate limiter on anything that flashes.

### D1 Datamosh (Notch Motion Datamosh, "Rammstein 2019 IMAG" look) - priority 1, L, perf est 1.5-3 ms
- **Look:** the picture stops updating where nothing is new, and motion from the incoming shot drags the old shot's pixels
  ("melting bloom"), blocky 8-16 px macroblock smears, colours stained by the frame before the cut. References: Notch
  Motion Datamosh node, Codrops Three.js datamosh demo (decoder emulation: suppress the intra refresh at a cut so old pixels keep
  being dragged), Modrinth datamosh shader (8x8 blocks sample from offset positions, per-macroblock update timing, DCT-style ringing).
  TD prior art in-repo: `TD-Toxes dataMosh_MYLES` (Y_td_toxes_myles.md, MIT, feedback + displace, only reads as datamosh on motion video).
- **Technique (codec emulation, since real codec motion vectors are impossible here):**
  1. Pass A (compute) **block matching**: per block (16 px at 1080x1920 = ~68x120 = 8,160 blocks), find the offset in +-R px
     minimising SAD between this frame and the previous *input* frame; write MV to an RG16F texture (block res). Hierarchical (half-res
     search first, then +-2 refinement) keeps cost near 0.5 ms; brute force +-16 at full res = ~600 M ops/frame (est 3+ ms, too slow).
  2. Pass B (compute) **mosh state**: `out = sample(prevOut, uv - MV*gain)` per pixel, i.e. the output is the previous *output*
     warped by the motion, not the new frame ("P-frame without residual"). Persist in a Feedback TOP (32F or 16F).
  3. **I-frame refresh:** blend `out` toward the live input with a per-block random schedule (`Refresh` blocks/frame) or fully on `Trigger`.
  4. **Bloom mode** (hold at a cut): at `Trigger`, freeze the *old* output and apply the *new* shot's MVs only (cross-mosh: motion from video B, pixels from A).
  5. Optional residual: add `(input - warp(prev))` scaled by `Residual` (0 = pure smear, 1 = normal video).
  6. DCT-ish blocking: quantise block corners with `Block Edge` ringing from a 2x2 sinc.
- **NOT possible here:** reading H.264 motion vectors / I-frame removal of the actual file; the Optical Flow TOP (T-18).
  Best emulation: above. Alternative cheaper flow: single-scale Lucas-Kanade on a 5x5 window (one compute pass, est 0.4 ms, noisier,
  fails on large motion) - offer as `Flow Method` menu: Block / LK / Frame-diff-gradient.
- **Pars (range):** Block Size {8,16,32}; Search Radius 2-32 px; MV Gain 0-3; Hold Decay 0-1 (how fast the stain heals); Refresh Rate 0-60 blocks/s*1000;
  Residual 0-1; Cross Source (TOP, optional); Chroma Bleed 0-1 (smear chroma further than luma, like 4:2:0); Quantise 1-32;
  Freeze Mask (TOP, e.g. person mask: moshing only the background or only the dancer); Mix 0-1; Trigger; Auto-Trigger on Beat; Reset.
  Modes: Bloom, Drag (continuous), Cross-mosh, Freeze-hold, Block-shuffle (random MV, no input needed).
- **Presets:** "P-frame drift" (16 px, gain 1.2, decay .98), "Bloom on beat" (trigger on kick, decay .92), "Cross-mosh A/B", "Chroma stain", "Mosh the background only" (mask = inverse person mask), "Glitch block shuffle" (random MVs, for generative sources).
- **Inputs:** TOP in, optional Cross/Mask TOP, CHOP (beat, level), effector Null (mosh only inside a radius).
- **Safety:** flash rate limiter (>3/s luminance changes capped), `Max Luma Step` clamp, Fail-safe Switch. J13 in J_interactive_camera_effects already ruled "not ranked (flash risk)": here it is cleared as a **non-flashing** effect when `Trigger` is rate-limited.
- **Extends:** `TD-Toxes dataMosh` is the cheap fallback inside this COMP (Mode "Drift-lite").

### D2 Pixel Sort (Sapphire PixelSort, Notch Pixel Sort, Universe Glitch) - priority 1, M, perf est 1-2 ms
- **Look:** streaks of sorted brightness along rows/columns/diagonals, cut by a threshold or edge mask (Kim Asendorf algorithm).
  Existing: `pixelSorting_MYLES` is **not** a real sort (Y_td_toxes_myles.md; "cheap smear").
- **Technique:** compute pass 1 marks intervals (luma between `Lo`..`Hi`, or edge-bounded); pass 2 one workgroup per row sorts each interval
  by key (luma / hue / saturation / R / G / B / noise). Sort per row in shared memory with a bitonic network (pad to 2048).
  **Risk:** shared-memory + barrier in TD's compute GLSL on MoltenVK is unverified; probe on the scratch TD first. Fallback: odd-even
  transposition via K single-pass compute iterations (K = 8-32, each 0.1 ms) giving a "partial sort" that looks like melting, which is
  visually fine and animatable (Sort Progress 0-1 = number of passes done).
- **Pars:** Direction (angle 0-360 or H/V/diag), Key (Luma, Hue, Sat, R, G, B, Random), Lo/Hi threshold 0-1, Mode (Threshold, Edge-bounded, Mask-bounded, Fixed Length), Interval Length 8-1080, Invert Order, Progress 0-1, Jitter, Mix; Reverse every other row.
- **Presets:** "Asendorf classic" (luma, Lo .25, Hi .8, vertical), "Melt-up", "Hue rainbow", "Beat-sorted" (Progress tied to audio level), "Edge fray".
- **Inputs:** TOP, optional mask TOP (person mask: sort only the performer), audio CHOP to Progress.

### D3 Shatter 3D + shard sim (Notch Voronoi Fracture + Rigid Body; Houdini RBD Voronoi Fracture) - priority 1, L, perf est 1-2 ms for 256-1500 shards
- **Look:** screen/subject cracks, then pieces fall, tumble, collide with a floor/performer and fade; "Thanos" and "glass break" variants.
- **Exists:** `td-port/shatter` = 2D per-pixel Voronoi shards, no physics, no history (offline-gated, TD runtime not run). That is **mode "2D Burst"** of this COMP.
- **New engine:** (1) Python builds a Voronoi (or radial-concentric crack) polygon set once per `Seed/Count` -> one SOP with N prims, per-prim `pivot`, `id`; a precomputed UV so each shard shows its piece of the picture.
  (2) **Shard state texture** (N x 4 RGBA32F rows: pos+vel, quat, angular vel, life) stepped by one compute pass: gravity, drag, floor plane with bounce + friction, impulse from `Trigger` (radial from impact point, or from the Effector Null), simple shard-shard separation is skipped (N^2) - use a hash grid only if needed.
  (3) A GLSL MAT vertex shader reads the state by prim id to place each shard; fragment samples the source TOP at the shard's original UV, adds edge darkening + a "crack" colour + thickness (extrude by Geometry COMP with 2 layers).
  (4) **Depth-image collision** (Notch "Rigid Body Depth Image"): optional depth TOP from `DC_depth_cam`; shard Z is pushed out of depth < D, so shards bounce off the performer. Person mask version = 2D only.
- **Modes:** 2D Burst (the td-port shader), Crack-only (static cracks growing from an impact point: crack distance = noise-warped Voronoi edge distance, grows with `Crack Progress`), Fall (full sim), Explode (outward), Implode (pull), Reverse-heal (assembles back: run the sim backwards from stored keyframes or use a spring toward home).
- **Pars:** Count 16-1500; Pattern (Voronoi, Radial, Grid, Triangles, Wood-splinter = elongated cells); Seed; Randomness 0-1; Gap 0-20 px; Crack Colour; Gravity -20..20; Bounce 0-1; Friction 0-1; Impulse 0-50; Spin 0-20; Fade Time 0-10 s; Heal Time; Impact X/Y (or Effector); Floor Y; Extrude 0-40; Source TOP + Bg TOP (what is behind the hole: black, a second clip, transparent for Arena).
- **Presets:** "Glass pane" (radial, 300, fade 2 s, bg = clip B), "Floor smash" (gravity, bounce .4), "Beat shatter" (trigger on kick, heal 0.6 s), "Thanos" (dust: see D4), "Wood splinters".
- **Gotcha:** transparent background output must be premultiplied for Arena (memory overlay-alpha-premultiplied).

### D4 Disintegrate / dust / Thanos (Houdini POP grains + noise dissolve; After Effects "Particle Playground", Trapcode Particular with a layer emitter) - priority 1, M, perf est 1-3 ms
- **Look:** the picture breaks into ash/pixel dust that blows off in a wind direction, edge-first, from a noise-threshold wave.
- **Technique:** a **dissolve front** = threshold (noise(x) + gradient along wind) vs `Progress`; pixels behind the front are emitted as particles: BO_particles' `Layer Emitter` from the TOP (position + colour from the pixel at spawn), initial velocity = wind + curl noise, life 1-4 s, size 1-3 px, colour from the source; the base image is masked by the same front (leaving edge glow: `Edge Glow` colour band).
  Particle count budget 262k = 4.7 ms already measured for BO_particles (STATUS), so use 64k-128k for this look.
- **Pars:** Progress 0-1 (animatable, beat), Wind Angle/Strength, Noise Scale/Speed, Front Softness, Edge Glow colour/width, Particle Count 16k-262k, Size, Life, Turbulence, Gravity, Direction mode (Left-Right, Radial, Top-Down, From Point/Effector, From Person Mask edge).
- **Inputs:** TOP, person mask (`bg_person_mask`, in progress), effector Null.
- **Reverse:** `Progress` back to 0 reassembles (particles lerp home with a spring) - "reconstruct" preset.

### D5 Broken screen / smashed LCD / dead-pixel (Resolume-adjacent LED-stage staple; ISF "Broken LCD" is MIT-credited in ISF-Files) - priority 2, S, perf est 0.4 ms
- **Look:** cracked-glass overlay with refraction, coloured ink blots, vertical and horizontal dead lines, dead-pixel clusters, flicker.
- **Technique:** crack lines from a distance-to-Voronoi-edge field (static pattern per Seed, grows from impact), refraction = displacement by crack normal, ink = colour noise with pre-multiplied alpha, lines = column/row stuck patterns.
- **Pars:** Crack Amount, Impact X/Y, Refraction 0-40 px, Ink Amount/Colour, Dead Lines H/V count, Dead Pixels density, Flicker Rate (rate-limited).
- **Presets:** "Dropped phone", "Bullet hole", "Dead LED wall" (for LED-stage fun, off by default on screens carrying the real show).

### D6 Blast / explosion burst (Universe "Bang"; Notch shockwave + particles) - priority 2, M, perf est 1-2 ms
- Radial shockwave (td-port shockwave already: **P**), expanding ring of displacement, particle sparks (BO_particles burst preset), light flash capped at 3 Hz and 25% area, smoke from fluid2d emitter at the impact (L: fluid2d), debris: shards (D3) given an outward impulse.
- This is a **macro COMP** wiring existing pieces: `Trigger` fires the shockwave, a burst, and the shard impulse together. Cheap to build once D3 and particles exist.

### D7 Melt / drip / liquify (Arena "Goo", Sapphire WarpPuddle / WarpDrops / WarpPuff, After Effects Liquify) - priority 1, S, perf est 0.4-0.8 ms
- **Technique:** feedback displacement field `D(t+1) = D(t)*decay + gravity_dir*luma_viscosity + curlnoise*turb + impulses`; output = source sampled at `uv - D`. Luma-weighted so bright areas run first (or a mask). One compute pass + Feedback TOP (RG16F).
- **Pars:** Gravity Angle/Strength, Viscosity Source (Luma, Inv Luma, Mask, Uniform), Turbulence, Decay (heal), Drip Streaks (vertical 1-D noise stretching), Rate, Impulse (Trigger + Effector), Stretch 0-3, Edge Behaviour (Clamp, Wrap, Mirror).
- **Presets:** "Wax melt", "Rain on glass" (Drips), "Acid trip" (turbulence high), "Bounce back" (Decay .9).
- **Extends:** FX_motion_trail is the colour-trail sibling; this is geometry trail.

### D8 Tile scramble / block displace (Sapphire TileScramble, RomanTile, Arena Fragment / Cube Tiles; Notch Randomise Tiles, Block Glitch) - priority 2, S, perf est 0.3 ms
- Per-tile hash decides: swap, shift, flip, hold last frame, colour offset. Tile grid size 4-256 px (non-square, non-uniform "bricks" and Voronoi cells variants). Rate = BPM-snapped or audio-triggered; Hold uses a Cache TOP so a tile freezes while others keep moving.
- Mode set: Scramble, Shift Rows, Shift Columns, Hold-and-release, Zoom blocks, Block RGB shift.

### D9 Corruption bank: JPEG / DCT damage, bit-flip, TV damage, scanline tear (Sapphire JpegDamage / DigitalDamage / TVDamage; Universe Glitch; Notch Bit Crush / Image Compression) - priority 2, M, perf est 0.8 ms
- **DCT block (real JPEG-style):** one workgroup per 8x8 block (32,400 blocks at 1080x1920), 64 basis dot products per pixel computed in shared memory; quantise with a `Quality` table; chroma subsampling toggle; **Corrupt** = zero/flip random coefficients per block => authentic blocky "JPEG damage". Cost: 32k blocks x 64x64 MACs = ~130 M MAC, ok on GPU; without shared memory, fall back to per-pixel 64-term sums (still ~130 M MAC/frame).
- **Bit-flip:** reinterpret channels as uint8, xor random masks on random rows/blocks (uint ops are allowed in compute GLSL).
- **TV damage:** horizontal tear (row offset noise with decaying bursts), vertical hold roll, line jitter, tape dropout streaks, head-switch noise at the bottom. VHS bundle = 5.1.
- **Pars:** Quality 1-100; Block 8/16; Corrupt Rate 0-1; Corrupt Mode (Zero, Flip, Swap, Shift Block); Chroma Subsample; Tear Amount/Speed; Roll; Jitter; Dropout Density; Seed.

### D10 Time-based destruction: time displace / time slice / echo-space (Sapphire TimeDisplace, TimeSlice, TimeWarpRGB; Universe Echospace; Notch Frame Delay) - priority 2, M, perf est 0.6 ms + memory
- **Technique:** Cache TOP holds N frames (64 x 1080x1920 RGBA8 = ~0.5 GB; use 16-32 and cap, or RGBA8 at half-res for the older frames); a compute pass picks for each pixel the cache index `i = f(luma(map), x, y, time)`; modes: Luma-displace, Slice (vertical bars with increasing delay = `SliceDelay` look; **P** slice_delay), Radial delay, RGB offset delay (Delay RGB), Echospace (N transformed copies with cumulative scale/rotate/hue).
- Exists: **P** echo, slit_scan, slice_delay, stutter. Extension: one `TD_timedisp` COMP that exposes all as modes sharing a single Cache.

### D11 Glass / refraction shatter shader (Notch Physical lens, Prism look) - priority 3, M
- Per-shard normal -> refraction offset + dispersion (3-sample RGB, three.js chunk MIT) + Fresnel rim. Folded into D3's fragment stage as `Glass` option; the Prism glass port exists (`td-port/prism_glass`, **P**).

### D12 Frame-difference "ghost destruction" / background subtract (Notch Frame Difference + Background Plate Subtract) - priority 3, S
- Cache last frame, absolute difference, threshold -> mask of moving things; feed into D1 as `Freeze Mask`, or glow it. N ops only.

## 4. After Effects / plugin suites mapped to TD

### 4.1 Trapcode (Particular, Form, Mir, Tao, Shine, Starglow, Echospace)
| Effect | What it does | TD status | Build / extend |
|---|---|---|---|
| **Particular** | Emitters (point, box, sphere, light, layer, grid), Physics (gravity, air with turbulence/spin, spherical field, bounce floor), **Aux system** (child particles per parent: trails, sparks), Particle sprite layers, size/opacity over life curves, motion blur, DOF, Fluid Dynamics extension | **L** BO_particles covers POP + compute engine, curl, audio, trails, instancing | **G-PART2** (M, prio 1): add Layer Emitter (TOP position+colour), Aux/child spawn (compute: parent death or per-N-frames spawns), life curves (Ramp -> lookup), sprite sheets + text particles, spherical field effector, DOF (per-point CoC, from BR_rubenfro), motion-blur streaks (velocity-length sprite). Mostly modules to add, not a new COMP. |
| **Form** | Grid of particles (Box/Sphere/OBJ), displaced by layer maps and fractal fields, audio-reactive, base form + Displacement + Fractal + Disperse | Arena Point Grid is the same idea; PX point-fx (in progress) is the modular version | **G-FORM** (M, prio 1): a `Grid Form` source for PX: grid/sphere/mesh sources, map displacement (TOP luma), fractal noise (curl / simplex 4D), Disperse (random drift), Twist, colour from TOP. Reuse px_requirements modules; this is a **PX source preset pack** not new code. |
| **Mir** | Wireframe / solid procedural 3-D meshes: terrain, fractal shapes, "Repeater Group", "Fractal Group", "Shader Group", "Rendering Group" (names from the help index) | none | **G-MIR** (M, prio 2): Grid SOP + displacement GLSL MAT (fractal noise, ridged, domain warp), wireframe via MAT edge shader or Line SOP, repeater = Instancing, fog/DOF; terrains also = Arena Terrain / Sphere. |
| **Tao** | Extrude geometry along a path, repeats (ribbons, helix, tubes), reflection maps | none | **G-TAO** (M, prio 3): Spline/Sweep SOP + Instancing (Python-built), env-map reflection via Cube Map. |
| **Shine** | Radial light rays from bright areas | **P** light_shafts | extend: colour ramp along ray, boost source, "radial gradient" modes |
| **Starglow** | 4-12-armed streaks from highlights, colour along arm | none | **G-STARGLOW** (S, prio 1): threshold, N directional blurs (each 1 pass with long kernel), colour ramp lookup by distance, additive; est 1 ms at 8 arms. Doubles as Sapphire Rays / Streaks / Glint / Glare. |
| **Echospace** | transform-chain echoes | **P** echo, **L** motion_trail | D10 mode |

### 4.2 Universe (80 GPU plug-ins; names from the help index)
- **Glitch / distortion:** Glitch, Chromatic Aberration, Chromatic Displacement, Prism Displacement, Heatwave, RGB Separation -> **P** glitch + rgb_split; Heatwave = noise-displaced refraction (D7 family); Prism Displacement = G-DISP (S).
- **Stylise:** Analog, **AV Club** (analog video: scanlines, bleed, noise), **VHS**, **Retrograde** (film/VHS retro), Holomatrix II (hologram scanlines + tint), Long Shadow, Luster, MisFire, Multitone, Noir, Dither and Palettes, Electrify (lightning edge glow), Ecto, ChromaTown, Carousel, Shrink Ray, Sketchify, **Symbol-Mapper** (ASCII/glyph mapping: **P** ascii), Texturize / Texturize Motion, Overlight, Knoll Light Factory EZ (lens flare). -> G-VHS (5.1), G-HOLO, G-LONGSHADOW (S each), G-LENSFLARE (M), G-ELECTRIFY (S).
- **Blur / glow:** Chromatic Glow, Compound Blur, Edge Glow, Glimmer, Glo Fi, Optical Glow, Point Zoom, Spot Blur, Quantum -> G-BLOOM + Starglow + Compound Blur (blur radius by map, S).
- **Text / HUD / MoGraph:** Hacker Text, Numbers, Screen Text, Text Tile, Title Motion, Type On, Typographic, 3D Stroke, Array Gun, Echospace, HUD Components, Line, Logo Motion, Progresso, Reframe -> **L** LK_typecore, urdu_type, lyrics_feed; HUD Components / Progresso / Numbers = G-HUD (M, prio 2: data-driven HUD widgets from CHOPs; ties to UI engine I_ui_engine.md).
- **Generators:** Fractal Background, Gradient Ramp, Soft Gradient Background, Spectralicious, Turbulence Noise, Maxon Noise -> G-GEN pack; Soft Gradient Background (mesh gradient) = prio 1 S (very trendy, Bezier/mesh gradient in GLSL).
- **Transitions (34 named):** Blinds, Bokeh, Camera Shake, Carousel, Channel Blur, Channel Surf, Clock Wipe, Color Mosaic, Cube, Diamond Wave, Dolly Fade, Flicker Cut, Fold, Glitch, Inside Cube, Rubix Cube, Shape Wipe, Slide, Swish Pan, Triangle Wave, Unfold, VHS, Warp... -> G-TRANS.

### 4.3 Boris FX Sapphire (names from the OFX picture index; groups seen: Glow, Light Beams, Lens Flares, Glints, Lighting, AutoPaint & HalfTone, Kaleidoscopes, Film, Edge, Emboss, Stylize, Adjust, Composite, Blur+Sharpen, Distort, Warps & Shake, Lightning Zaps, Gradients/Grid/Shape, Procedural Textures, Time, Transitions)
| Group | Effects | TD status | Gap id |
|---|---|---|---|
| Glow | Glow, GlowAura, GlowDarks, GlowDist, GlowEdges, GlowNoise, GlowOrthicon, GlowRainbow, GlowRings, UltraGlow, ZGlow | N Blur+Add | G-BLOOM modes (Edges, Noise, Rainbow = hue-ramp by distance, Rings) |
| Beams | Rays, EdgeRays, Streaks | **P** light_shafts | Starglow |
| Lens | LensFlare, LightLeak, Glint, GlintRainbow, Glare, Flashbulbs, BokehLights, Light3D, SpotLight | none | **G-LENSFLARE** (M): ghost chain along axis through screen centre (Shadertoy "lens flare" family; licence per file), light leaks = animated colour noise + blend screen; bokeh = hex-kernel blur of highlights |
| Paint | AutoPaint, Sketch, Etching, Brush:Oil, Brush:Chalk, Crosshatch, Cartoon, CartoonPaint, Posterize, HalfTone(+Color, Rings) | P halftone; Kuwahara = oil; edge = N | **G-PAINT** (M): Kuwahara (anisotropic), cross-hatch (tonal art map), cartoon (posterise + edge), stipple |
| Kaleidoscopes | Kaleido:Triangles/Squares/Diamonds/Oct, KaleidoPolar/Radial, FlysEyeCircles/Hex/Rect, TileScramble | **P** kaleido (one type) | G-KALEIDO2 (S, mode menu; reuse P code) |
| Film | FilmEffect, FilmDamage, Vignette, BleachBypass, Grain(Static, Ultra), Diffuse, VintageColor2/3Strip | P vignette; grain = N | **G-FILM** (S): dust, scratches, gate weave, flicker (low amplitude), bleach bypass, 2/3-strip colour matrix |
| Edge / Emboss | EdgeDetect(Double), EdgesInDirection, EdgeColorize, Emboss(Shiny, Distort, Glass) | N Edge/Emboss | S bundle |
| Stylise | BandPass, ColorFuse, DogVision, DigitalDamage, JpegDamage, TVDamage, Grunge, Mosaic, **PixelSort**, PseudoColor, **PsykoBlobs**, **PsykoStripes**, PrismLens, RomanTile, ScanLines, Solarize, StripSlide, Zebrafy, ZFog | partly | D2, D8, D9; PsykoBlobs/Stripes = animated colour pattern generators (S); Zebrafy = banded luma (S); PseudoColor = palette_map |
| Distort | Distort, DistortBlur, DistortChroma, DistortRGB (Distort warps by the gradient of a lens input) | N Displace | pattern: "Displace from map gradient" = G-DISP (S) |
| Warps | InfiniteZoom, ParallaxStrips, WarpBubble(2), WarpChroma, WarpCornerPin, WarpDrops, WarpFishEye, WarpMagnify, WarpPerspective, WarpPolar, WarpPuddle, WarpPuff, WarpRepeat, WarpTransform, WarpVortex, WarpWaves(2), Shake, StretchFrameEdges | **P** shake, ripple, shockwave | **G-WARP** bank (one COMP, mode menu, each mode a few lines of UV math; Drops/Puddle = D7 with ring seeds) |
| Zaps | Zap, ZapTo, ZapFrom, UltraZap, DissolveZap | none | **G-ZAP** (M, prio 2): lightning between two points (midpoint-displacement recursion built in Python as SOP polyline, or GLSL fractal line SDF with domain noise), glow + flicker, branches; pointers: laser_path COMP for geometry |
| Time | FreezeFrame, GetFrame, JitterFrames, RandomEdits, ReverseClip, TimeAverage, TimeDisplace, TimeSlice, TimeWarpRGB, Retime | **P** stutter, echo, slit_scan | D10; Retime/optical time-remap is the AX "Twixtor-style" community TOP (uisato, N_community) |
| Transitions | Dissolve* and Wipe* families, FilmBurn, StripSlide, ParallaxStrips | none | G-TRANS |
| Procedural | Caustics, Sparkles, TextureCells ... (page truncated) | partial | G-GEN: Caustics (Voronoi-based), Cells (Worley) |

### 4.4 Other AE/Magic Bullet / Element 3D style looks
- **Magic Bullet Looks / Colorista** grading: Lookup TOP + curves + lift/gamma/gain wheels in a `FX_grade` COMP (S, prio 2). **Film Convert / LUT** library import: Lookup TOP, `.cube` loader (S).
- **Element 3D look** (extruded text/logos with PBR + reflections): TD Render TOP + PBR MAT + Environment Light; PRISM logo kit and `urdu_type` extrusion = Slug / Geometry COMP. Not a gap in ops; a gap in a **look template COMP** `EL_logo3d` (M, prio 2: extrude, bevel, chrome, env map, animated light sweep; PF26 direction B "chrome, glass and gold 3D").
- **Real Lens Flares / Optical Flares:** G-LENSFLARE.
- **Depth of field / Z-defocus:** Sapphire ZDefocus, RackDefocus, DefocusPrism -> with `DC_depth_cam` / depth estimation: **G-DOF** (M, prio 2): variable-radius disc blur by depth, hexagonal bokeh kernel, bokeh highlight boost (2-pass compute at half-res).

## 5. VDMX / ISF, Houdini, Niagara, Cavalry / Rive - concepts to bring over

### 5.1 Small-bundle effects (S each, one COMP per bundle with a Mode menu)
- **G-DITHER:** Bayer 2/4/8, blue-noise threshold, Riemersma-like "diffusion" (true Floyd-Steinberg is sequential; use blue-noise + error-ish noise), palette (1-bit, 4-colour Game Boy, CGA, custom hex list), pixel size; ties to palette_map (L) and Notch Dither / Universe Dither and Palettes. Prio 2.
- **G-VHS:** per-line horizontal jitter, chroma bleed (shift + blur chroma only), tracking noise band that rolls, head-switch tear at the bottom, dropout streaks, tape-wobble, scanlines, overlay noise, interlace combing for motion, date stamp overlay (Text TOP). References: Notch VHS Scanlines + VHS Blur, Universe AV Club / VHS / Retrograde, v002 Glitch Analog (ISF in VDMX, adapted). Perf 0.5 ms (2 passes). Prio 1.
- **G-CRT:** shadow mask (aperture grille / slot / dot), curvature, bloom, scanline beam profile (Gaussian per line), phosphor persistence (Feedback), moire-safe at 1080p. Check `td-port` CRT status (pending port in INVENTORY). Prio 2.
- **G-HOLO:** hologram: RGB-offset scanlines, vertical flicker, scan bar, tint, fresnel edge from a luma edge. Prio 2.
- **G-ASCII/GLYPH:** exists as **P** ascii; extend: custom glyph atlas, per-glyph colour from source, glyph size from luma, matrix rain (Hacker Text look). Prio 2.
- **G-HEAT, G-BEND, G-SMEAR, G-TRI, G-INFZOOM, G-AUTOLEVEL, G-DISP, G-LONGSHADOW, G-ELECTRIFY, G-SPARKLE:** each 20-80 lines GLSL, 0.1-0.4 ms, difficulty S, prio 3 except G-INFZOOM (2).

### 5.2 Framework items (the real value of "software emulation")
- **G-FIELD (prio 1, M): Falloff / Field generator.** From Notch Fields, Cavalry Falloffs, Houdini attribute ramps. A COMP outputting a **single-channel 1080x1920 field TOP** with shapes: Linear, Radial, Box, Ring, Noise (curl/simplex/Worley), Image/Luma, Person Mask, Audio-driven waves (spectrum along x), Time wave (moving bands), plus **combine ops** (add, multiply, max, smoothstep, invert, remap curve). **Every effect in this file takes an optional `Field` input that multiplies its Amount** (D1 mosh only inside the field, D3 crack only near the impact, D7 melt only where the field > 0). Also an `Effector Null` -> field adapter (gizmo = sphere/box in 2D). Matches px_requirements.md (Null / box effectors with gizmo). Perf 0.1-0.3 ms.
- **G-STACK (prio 2, M): Resolume-style effect chain COMP** - a drag-in list of lab FX COMPs with bypass, order, per-slot mix; `td_layer_mixer` already does layers; this is the effect-stack sibling (Arena effect rack). Use the PX "add/remove/reorder modules" rule (CLAUDE.md PX). Shares the preset system of zkit.
- **G-ISF (prio 1, M, tool): ISF -> GLSL TOP importer** (`td_isf` or extension of `td_shadertoy`). ISF = GLSL + JSON header (INPUTS with ranges/types, PASSES with TARGET + PERSISTENT buffers). VDMX ships ~200 ISF; Vidvox ISF-Files repo (MIT, 364 files, per-file caveats already in L_shader_sources_licences.md); each ISF becomes a GLSL compute TOP + custom pars from INPUTS (ranges free!). Converts the entire VDMX / VJ ecosystem of filters in one tool; the Quartz Composer era's classics are already ISF. Risk: ISF uses fragment-style `gl_FragCoord`, `IMG_THIS_NORM_PIXEL`; multi-pass ISF -> compute mode chain (T-47).
- **G-CLONE (prio 2, M): Cloner COMP** (Arena Linear / Radial / Grid cloner, Notch Clone nodes, Cavalry Duplicator): N instances of a TOP or geometry in a grid/ring/line/spline/random, per-instance falloff-driven transform + colour from G-FIELD, time offset per instance (Cache). TD: Instancing on a plane or a GLSL TOP tiled composite; with fields = Cavalry-style "effector" stack (Noise, Stagger, Oscillator, Spring, Time).
- **G-SPRING / procedural motion (prio 3):** Cavalry / Rive behaviours -> a CHOP bank `MO_motion` (Spring, Stagger by index, Oscillator, Noise, Modulate, Follow-through, Overshoot easing, Time Effector), writes to any COMP par via parexec; TD's Lag / Filter / Spring CHOP cover the core already; build only the packaging. Rive's state-machine UI ~ `ZC_control_surface` + `CQ_cuelist`.

### 5.3 Houdini looks (K = from general knowledge)
- **POP grains / sand (K):** granular sim: 2D = compute with a grid hash, 20-50k grains, friction + collision with a mask (the performer). Prio 3, L. Approximated by BO_particles with collisions against the person mask / depth.
- **RBD Voronoi fracture + constraint network (K), Unreal Chaos GC (SideFX docs):** D3 above; **glue constraints that break** = per-shard neighbour list + break strength vs impulse; "damage threshold" levels (SideFX: fracture to the highest damage threshold first, then assign cluster levels) = two-level fracture (big pieces break into smaller ones on second hit): optional Level 2 in D3. Prio 2 (L).
- **Vellum (K):** cloth done (**L** BN_cloth); Vellum grains/hair/balloon = extension of cloth; balloon (pressure constraint) prio 3.
- **Pyro / FLIP (K):** 2D smoke = **L** fluid2d; 3D pyro = volume raymarch of a 64^3-128^3 texture (T-46 caution); prio 3, L.
- **Copy to Points + attribute noise (K):** exactly the PX modular point-fx pipeline (**in progress**).

### 5.4 Unreal Niagara (K)
Modules to mirror in BO_particles: Curl Noise Force (L), Vector Field, Ribbon renderer (trails as ribbons; BO has trails), Mesh renderer (Instancing), **Grid2D Gas** (fluid2d), Neighbor Grid 3D (boids / SPH), Data Interface "Audio Spectrum" (AC_audio), Texture Sample DI (G-PART2 Layer Emitter), **Niagara Fluids** (prio 3). The Epic **Chaos Destruction** model (Geometry Collection pieces + damage thresholds + fields) matches D3. Note: StageLab has an open question "Unreal yes/no" (STATUS) - none of this needs Unreal.

## 6. Ranked gap list (what to add), with already-built extensions

Priority 1 (build first for live visuals) - total about 11 items:
| # | Id | Effect | Diff | Est perf @1080x1920 | Why |
|---|---|---|---|---|---|
| 1 | G-FIELD | Falloff / field generator + effector adapter | M | 0.1-0.3 ms | Multiplies the value of every other effect; Notch/Cavalry/Houdini idea |
| 2 | D1 | Datamosh (block-match + hold + cross-mosh) | L | 1.5-3 ms | The user's ask; Rammstein IMAG look; needs flash limiter |
| 3 | D3 | Shatter 3D + shard sim (+ glass cracks, depth collision) | L | 1-2 ms | The user's ask; extends td-port shatter |
| 4 | D4 | Disintegrate / dust | M | 1-3 ms | The user's ask; reuses BO_particles + person mask |
| 5 | D7 | Melt / drip / liquify | S | 0.4-0.8 ms | Cheap, high wow, Arena Goo / Sapphire Puddle |
| 6 | D2 | Pixel sort (true sort) | M | 1-2 ms | Trend (FKJ tour, Notch), MYLES version is not a real sort |
| 7 | G-VHS | VHS / analog video | S | 0.5 ms | Everyone uses it; Universe AV Club |
| 8 | G-STARGLOW | Star streaks / glints | S | ~1 ms | Sapphire + Trapcode staple |
| 9 | G-ISF | ISF importer tool | M | n/a (tool) | Unlocks ~200+ VJ filters at once |
| 10 | G-FORM / G-PART2 | Form grid look + Particular modules (layer emitter, aux, life curves) | M | per BO/PX budgets | Trapcode looks on the existing engines |
| 11 | G-BLOOM | Bloom / glow family | S | 0.5 ms | Arena Bloom, Notch Glow, Sapphire UltraGlow |
| 12 | D9 | DCT / bit-flip corruption bank | M | 0.8 ms | Sapphire JpegDamage |
Priority 2: D5 broken screen, D6 blast macro, D8 tile scramble, D10 time displacement hub, G-STACK, G-CLONE, G-TRANS (transitions), G-PAINT (Kuwahara / hatch), G-LENSFLARE, G-KALEIDO2, G-WARP bank, G-DITHER, G-CRT, G-HOLO, G-FILM, G-ZAP, G-DOF, G-HUD, G-MIR, EL_logo3d, FX_grade.
Priority 3: D11 glass, D12 frame-difference ghost, G-TAO, POP grains, balloon / pyro, G-SPRING, remaining S micro-effects.

### Already built - how to extend (do not re-propose as new)
- **FX_strobe:** add Arena "Stroboscope" generator modes, Sapphire FlashBulbs; keep the flash limiter.
- **FX_motion_trail:** add Echospace transform chain (cumulative scale / rotate / hue per echo), Universe "Iterate".
- **FX_palette_map:** add Sapphire PseudoColor, Heat ramp (thermal), Zebrafy, Multitone / Tritone, LUT loader.
- **TP_test_pattern:** nothing new from this topic.
- **BO_particles:** G-PART2 list; D4 / D6 consume it.
- **BN_fluid2d:** Heatwave / Wave Warp / D7 derive their curl field from its velocity; smoke for blasts.
- **BN_cloth:** Vellum balloon / grains modes.
- **BL_cloud_morph + BL_splat_render, PX point-fx:** Form look, D4 dust, "Layer Emitter".
- **FT_face_track, DC_depth_cam, person mask (in progress):** feed masks into D1 / D3 / D4 / D7 and into G-FIELD.
- **BN reaction-diffusion + physarum (in progress):** Notch Reaction-Diffusion parity; use as G-GEN sources.
- **td-port effects not yet in TD (pending):** Datamosh, Feedback, PixelSort, CRT, Bloom, VHS, Grain, Neon, Contour, Reducto, Displace, Constellation, Fan Cam, FaceMosaic are named "Pending port" in `td-port/INVENTORY.md` (these are StageLab FFGL names with specs in `stagelab/`; the TD versions are not built). Read their StageLab specs (`stagelab/docs/specs/`) first and reuse the parameter set when building the TD versions so Arena and TD behave alike (CLAUDE.md effects: research first).
- **td-port with TD ports already ("P"):** ASCII, Echo, Glitch, Halftone, Kaleido, Motion Trail, RGB Split, Ripple, Shake, Shatter, Shockwave, Strobe, Tile, Transform, Tunnel, Vignette, Slice family (Chase, Color, Delay, ID, Life, Ripple, Spread, Tile, Tiler, Trim), SlitScan, Stutter, Spectrum, Light Sweep, Light Shafts, Color Warp, Hit, HitSlice, PixelFX, PersonKey, DepthFX, FlowFX, CrowdEnergy, CameraSliceReveal, LogoBuild, Prism glass, Rutt lines, Ink flow, Beam FX, Video relief, Elastic lens. Most are "offline gate passed, TD runtime not run" per td-port/STATUS.md: verifying them live is cheaper than rebuilding.

## 7. Build notes common to the priority-1 set

1. **One pilot first** (CLAUDE.md "save time"): G-FIELD (smallest, needed by the rest), then D7 (small, validates the feedback-displacement pattern), then D1 / D3 / D4 in parallel lanes (<= 2-6 live builders, park idle COMPs).
2. **Probe on the scratch TD first:** (a) shared-memory + `barrier()` in compute GLSL under MoltenVK (decides D2 bitonic vs transposition, D9 DCT), (b) uint bit ops in compute (D9), (c) RGBA32F image store/load in compute for the state textures (D3 shard rows), (d) compute dispatch size at 1080x1920 for the block-match pass (D1). Record results as T-nn.
3. **Cooking cost control:** all of these get `Quality` (Full / Half / Quarter internal res) and cook only when output is used.
4. **Safety:** D1 / D4 / D6 / D8 / D9 flashing paths carry the rate limiter + fail-safe Switch; transparent-output COMPs premultiply for Arena.
5. **Presets:** zkit preset bank per COMP (at least 5 presets each as listed in the cards), MIDI-mappable (td_midi_*), OSC-exposable (td_osc_expose).
6. **Demo media:** datamosh needs motion video; if the user's clips lack it, fetch free demo clips into `media/demo/motion/` with SOURCES.md (CLAUDE.md demo-media rule).
7. **Licences:** this file copies nothing; any Shadertoy pointer (Kuwahara, lens flare, crack patterns, mosh) is read for maths and re-written clean-room; ISF-Files are MIT per file with caveats in L_shader_sources_licences.md.

## 8. Open questions for the user

1. Is a **non-flashing, rate-limited datamosh** acceptable on stage visuals (J13 was parked for flash risk), or IMAG-only / off-stage use?
2. D3: transparent shards over a second clip (Arena alpha) or only inside TD (opaque bg)?
3. G-ISF: is converting third-party ISF files (per-file licence) OK beyond the MIT Vidvox-authored set?
4. Priority check: which of the 12 priority-1 items first? Suggested order is the table order.
5. Unreal yes/no (pending in STATUS) does not block anything here.

## 9. Nothing run, nothing changed

TD, Arena, REST, OSC and Syphon were not touched. Only read-only filesystem listings of `/Applications/Resolume Arena/` and `strings` on its binary (names only) were used; no downloads except web page text. Scratch strings dump lives in the session scratchpad (not in the repo).
