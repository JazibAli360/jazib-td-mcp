# Tutorials slice 03 (listing pages 12-17, derivative.ca tutorials, newest first)

Read 26 Oct 2026 by one Sonnet agent. TD target: 2025.31550 (macOS). Every op name below was checked against the live build (`dir(td)`, 681 classes) and `INDEX_2025.31550.json`.

- Tutorials read: **95** posts (pages 12-17, all `type[]=23`); 92 posts with a YouTube video (91 unique ids: posts 71003/71011 share one), 1 Vimeo lecture, 2 posts with no video link (70852, 70519).
- Video metadata (yt-dlp `--dump-json`): 91/91 fetched (title, channel, duration, views, likes, chapters, description). About 34 h of video in total.
- Transcripts: **14 fetched** (VTT + plain `.txt` in `research_src/tutorials/transcripts/`), 77 failed. Cause: YouTube answered HTTP 429 on the subtitle (timedtext) endpoint after the first 11 videos, while metadata calls kept working. The brief's stop-5-minutes-and-retry-once rule was followed three times (11:17, 11:43, 11:50); it persisted, so the rest of the slice is page data + video chapters + description.
- Evidence level per entry is in each JSONL row (`evidence`: transcript | chapters | description | page). Only transcript-backed entries carry spoken parameter values; chapter-based entries list ops implied by chapters/description and are marked as such.

## Counts per category
camera/interactive 16, TOP 12, workflow 11, GLSL 11, 3D/render 10, audio 7, ML/AI 6, output 6, POP 5, SOP 3, mapping 2, typography 2, CHOP 1, other 1, COMP/UI 1, Python 1.

Relevance (0-3 general TD mastery): 3: 44, 2: 39, 1: 12.

## Top 15 as rebuild recipes
Recipes 1-12 come from full transcripts; 13-15 from chapter outlines + descriptions (no transcript).
**1. Audio Reactive Particles using TouchDesigner POPs (elburz, 2026-10-19, post 75525, transcript)**
- Ops: pointgeneratorPOP > geometryCOMP > cameraCOMP > lightCOMP > renderTOP > nullTOP > transformTOP > lineMAT > randomPOP > attributePOP > particlePOP > mathcombinePOP > trailPOP > rayPOP > noisePOP > audiofileinCHOP ...
- Render rig: pointgeneratorPOP -> geometryCOMP + camera + light + renderTOP -> null -> transformTOP black bg; lineMAT with draw points on
- particlePOP after the generator; set the Particle POP feedback target to a null POP (named end) placed after the in-loop ops so everything between feeds back; birth rate and life expectancy set emission
- Source sphere tiny; randomPOP (size 3, min -1) writes a direction attribute N; map N to the particle initial velocity (particle input-attribute map)
- attributePOP creates Color (orange); then tick Color in particlePOP "input attributes" or it will not be carried
- Gravity: inside the feedback loop a mathcombinePOP subtracts (P.y - age*0.1 as pre-math "gravity") from position Y each frame
- (+4 more steps in the JSONL `build_steps`)
- Key params: birth rate: 50..1000 driven by level; max particles: raise it or flicker appears; gravity: age*0.1 pre-math; trail: match by PartId, short length; render pixel format: 32-bit float for post
- Trick: particlePOP is a feedback system: ops inside its target loop persist; custom attributes must be ticked in "input attributes"
**2. AURA FLOW - TOUCHDESIGNER TUTORIAL [34] (pao.olea, 2026-10-20, post 75535, transcript)**
- Ops: pointgeneratorPOP > noisePOP > trailPOP > keyboardinCHOP > lookuptexturePOP > rampTOP > pbrMAT > noiseTOP > nullTOP > twistPOP > lfoCHOP > mathCHOP > geometryCOMP > cameraCOMP > lightCOMP > renderTOP ...
- pointgeneratorPOP (torus, 3000-5000 pts) -> noisePOP (animate translate with absTime.seconds*0.1) -> trailPOP (increase length; use points/prims type)
- keyboardinCHOP key 1 pulses the Trail POP reset (resetting needed whenever point count changes)
- Colour: second noisePOP with combine operation None writing a new attribute "noisecolor"; lookuptexturePOP maps noisecolor through a rampTOP and writes Color; animate noise with absTime.seconds
- pbrMAT on geometry, environment light fed by a noiseTOP (period 5) -> null; specular level 1, metallic low, roughness low
- twistPOP x2 (taper in X/Y); strength of one driven by lfoCHOP -> mathCHOP (-50..150), speed 0.75
- (+3 more steps in the JSONL `build_steps`)
- Key params: points: 3000-5000 (2000 on slow machines); colour ramp HSV: orange (H25,S.95,V.8), pink-ish (H42?), purple (H249,S.69); noise period (color): 1; trail increment: 0.5
- Trick: trails recompute when point count changes: bind a key to the Trail reset pulse
**3. Body Tracking Interactive Triggers in TouchDesigner (elburz, 2025-04-29, post 71846, transcript)**
- Ops: sphereSOP > boxSOP > torusSOP > geometryCOMP > cameraCOMP > renderTOP > substanceTOP > pbrMAT > patternCHOP > nullCHOP > limitCHOP > mathCHOP > constantCHOP > trimCHOP > attributecreateSOP > transformSOP ...
- 3 geometries (sphere, box, torus) each in a geometryCOMP, shared camera, render; 3 substanceTOP copies (concrete, metal ...) dropped into 3 pbrMATs; attributecreateSOP adds tangents (needed for normal maps)
- Carousel index: patternCHOP ramp (length 3, range 0..2) -> null -> limitCHOP (loop 0..3) ; a constantCHOP + mathCHOP add offsets; 3 trimCHOPs (abs) give indices; mathCHOP range e.g. -3..3 = X positions into each geometry TX
- lagCHOP with "lag per sample" ON + overshoot animates between positions; ramp TOP circular vignette (over, swapped order)
- MediaPipe.tox (external, relative path) + hand tracking comp; turn off unused flags (performance); select hand 1 index_finger_tip* -> normalized 0..1 x/y; circle TOP marker needs -0.5 offset
- Positional swipe: logicCHOP outside bounds (about >0.8 for right, mirrored <0.2 for left) -> chopexecuteDAT off-to-on: par.value0 += 1 / -= 1 on the carousel constant
- (+3 more steps in the JSONL `build_steps`)
- Key params: timer debounce: 0.5 s; swipe zones: x about <0.2 / >0.8 (0..1); slope sensitivity: ~1.5, filter 0.25; index range: 0..2 loop to 3
- Trick: lagCHOP needs "lag per sample" ON even for single-sample channels
**4. Chaser Effect - Projection Mapping Tutorial (marcok06, 2025-04-14, post 71750, transcript)**
- Ops: moviefileinTOP > switchTOP > nullTOP > timerCHOP > countCHOP > nullCHOP > feedbackTOP > levelTOP > compositeTOP > resolutionTOP > outTOP > baseCOMP > windowCOMP > palette:Stoner > palette:CantonMapper
- Photo of the real surface; in Photopea (browser) create a canvas at projector resolution (1280x800), magic-wand each shape, copy/paste to layers, group layers per colour group, export layers as PNGs
- TD: all PNGs of one group -> switchTOP -> null; timerCHOP (length 1, cycle on, cycle limit off, only cycle pulse out) -> countCHOP (limit loop, max = len(op("switch1").inputs)-1) -> null -> switch index
- Trail: feedbackTOP -> levelTOP (opacity ~0.9 or less) -> compositeTOP over with the switch output -> back to feedback target; resolutionTOP with 32-bit float pixel format removes the permanent ghost
- Collapse the chain into a base, duplicate per shape group, replace inputs, composite all with over; enable/disable groups, tune timer length per group
- Mapping: palette Stoner (corner/warp) + Canton mapper (mask, free-form tool, projector resolution, output monitor toggle) + windowCOMP on projector monitor; first feed a reference image to align the Stoner, then swap in the eff...
- Key params: timer length: speed of chase; level opacity: trail length (lower = shorter); pixel format: 32-bit float to kill ghosting; projector res: 1280x800 (example)
- Trick: the length of the switch is read live with len(op("switch1").inputs) so adding shapes needs no edits
**5. Cooking & Performance Tutorial (tekt, 2025-05-25, post 72014, transcript)**
- Ops: constantCHOP > filterCHOP > mathCHOP > nullCHOP > switchTOP > moviefileinTOP > noiseTOP > palette:PerformanceMonitor
- Middle-click any op: Total Cooks count shows who is actually working
- Rule 1 always cook: output ops (audio stream out, windows, network out) cook every frame while active
- Rule 2 cook if asked: filterCHOP etc. cook when a downstream op or an active viewer pulls them
- Rule 3 on change: math CHOP cooks only when an input cooked or a parameter changed
- Reorder: do the cheap/on-change math before the always-changing filter, or filter last, so fewer ops cook
- (+3 more steps in the JSONL `build_steps`)
- Key params: default fps: 60; filter in perf monitor: needs * on both ends
- Trick: cook counts are the ground truth for what runs
**6. GLSL Effect Porting in TouchDesigner (elburz, 2025-05-15, post 71961, transcript)**
- Ops: glslTOP > constantTOP > feedbackTOP > nullTOP > opviewerCOMP > panelCHOP > selectCHOP > mathCHOP > resolutionTOP
- Plan: Shadertoy tabs Buffer A + Image + Common -> glslTOP "bufferA" and glslTOP "image"; bufferA output -> image input 0; bufferA output -> feedbackTOP -> bufferA input 0 (feedback target = bufferA glslTOP); constantTOP alpha 0...
- bufferA pixel format 32-bit float RGBA (data buffer, not 0..1 colour); image output 8-bit
- Syntax port: iChannel0 texelFetch -> texelFetch(sTD2DInputs[0], ...); mainImage(out vec4, in vec2) -> `out vec4 fragColor; void main(){ vec2 co = gl_FragCoord.xy; ...}`; final colour wrapped in TDOutputSwizzle(...)
- `Common` tab constant (cube size) becomes `uniform float size;` in both shaders, set on the Vectors page
- Resolution: drive res (e.g. 1024x1024) from one param so buffer and image match; reset feedback after resolution change
- (+2 more steps in the JSONL `build_steps`)
- Key params: bufferA format: 32-bit float RGBA; image format: 8-bit fixed; resolution: 1024x1024
- Trick: panelCHOP u/v gives normalized mouse inside the output only, easier than mouseinCHOP + math
**7. Interactive Art in TouchDesigner (elburz, 2025-05-22, post 72003, transcript)**
- Ops: containerCOMP > opticalflowTOP > compositeTOP > addTOP > nvidiabackgroundTOP > thresholdTOP > glslTOP > feedbackTOP > noiseTOP > baseCOMP > moviefileinTOP
- Make each interaction (panel drawing, LIDAR texture, webcam motion, NVIDIA background remover, threshold of face) its own component that outputs a texture
- Concatenate (add) the interaction textures into one layer; optional per-layer treatment
- Run opticalflowTOP on the video OR on the interaction layer: slope of motion becomes force that emits particles
- Jump flood algorithm (David Braun) turns the interaction mask into a distance field for particle forces; noise force and emission from GLSL particles (his "Mastering GLSL for TouchDesigner" course)
- Parameterise everything with custom parameters; a master resolution parameter lets a deployed piece adapt to a changed LED wall/venue; externalize + git
- Key params: architecture: texture-space interactions -> one layer -> optical flow -> GLSL particles
- Trick: optical flow of the interaction layer (not the camera image) makes particles emit "from thin air"
**8. Using the New Timecode Features in TouchDesigner (elburz, 2026-10-23, post 75551, transcript)**
- Ops: moviefileinTOP > audiofileinCHOP > audiodeviceoutCHOP > opexecuteDAT > chopexecuteDAT > edgeTOP > lensdistortTOP > lookupTOP > rampTOP > switchTOP > nullTOP > levelTOP > timerCHOP > mathCHOP > nullCHOP > blurTOP
- Import video + chime + song; audiodeviceout each; chime repeat off (pulse cue)
- Effects: edgeTOP, lensdistortTOP, lookupTOP(+ramp red->blue) and the clean video into a switchTOP (index 0 = clean) -> level -> null
- opexecuteDAT monitor ops = the video, enable Post Cook (runs every frame): `vt = changeOp.timecode; vt.frame, vt.second, vt.minute, vt.hour, vt.fps (29.97), vt.totalFrames, vt.totalSeconds`
- Gate on exact seconds with a global flag (otherwise action fires 30x per second): `if vt.second == 5 and not done: ...`
- Audio: chopexecuteDAT with "while on" and execute once per frame (value change off); `song.timecode` gives the same fields; use thresholds like totalSeconds >= 160 plus a global `fadeOut` flag so the Timer is pulsed only once
- (+1 more steps in the JSONL `build_steps`)
- Key params: video fps: 29.97 (~30); chop execute: while on, once per frame
- Trick: use post-cook, not pre-cook, for the freshest timecode
**9. Jen Stark-Inspired Colour Drip Effect in TouchDesigner (elburz, 2025-04-15, post 71765, transcript)**
- Ops: rectangleTOP > compositeTOP > feedbackTOP > rgbkeyTOP > nullTOP > transformTOP > keyboardinCHOP > hsvadjustTOP > displaceTOP > noiseTOP > noiseCHOP > nullCHOP > edgeTOP > monochromeTOP > palette:RGBContrast
- rectangleTOP 1280x1280 (free-licence max), size x 1 y 0.1, center y 0.5, colour red (use a TOP colour or feedback goes white)
- compositeTOP over -> feedbackTOP; target = composite; null for display; keyboardinCHOP "1" resets the feedback
- Inside the loop: transformTOP translate y -0.002 per frame and scale x 0.99 (narrower as it falls); hsvadjustTOP hue offset ~5-8 per frame
- displaceTOP with a noiseTOP (output = input resolution, monochrome off) weight ~0.002 so edges wobble in all directions; seed from a CHOP random (noiseCHOP/seed -> null) on reset
- RGB contrast (palette image filters) raised to 100 for hard colour bands; edgeTOP on comp with black edges, strengthen sample step
- (+1 more steps in the JSONL `build_steps`)
- Key params: translate y: -0.002; scale x: 0.99; hue offset: 5-8; displace weight: 0.002; rgb contrast: 100
- Trick: use a TOP colour at the loop start else feedback turns white
**10. Instancing with the Event CHOP in TouchDesigner (elburz, 2025-05-21, post 71993, transcript)**
- Ops: tubeSOP > transformSOP > nullSOP > geometryCOMP > phongMAT > cameraCOMP > lightCOMP > renderTOP > eventCHOP > keyboardinCHOP > selectCHOP > scriptCHOP > trailCHOP > constantCHOP > nullCHOP
- tubeSOP orientation Z + end caps on -> transformSOP uniform scale 0.025 -> null -> geometryCOMP; phongMAT with blending transparency on; camera tz 1.75; renderTOP 1024x1024
- eventCHOP: first input = trigger channels (0->>0 spawns an event; keyboard/MIDI), output channels id (-1 when idle), index (which trigger channel), onoff, input (trigger value, e.g. velocity), time, adsr, state (0-1 attack, 1-2...
- Total lifetime = sum of ADSR times (7 s in demo); trailCHOP is handy to visualise envelopes
- Point positions of a grid chosen with Python per event index; Select CHOP isolates ID/ADSR; instancing with null translate (TX/TY from event position), scale and rotation channels from ADSR; alpha from ADSR; post-processing at ...
- Key params: render: 1024x1024; tube scale: 0.025; event id idle value: -1
- Trick: the same network responds to MIDI notes: velocity arrives in the input channel
**11. Rolling Tiles using POPs, CHOPs, and DATs (vtln, 2026-10-20, post 75531, transcript)**
- Ops: containerCOMP > parameterCHOP > mathCHOP > nullCHOP > gridPOP > fieldPOP > patternCHOP > tableDAT > beatCHOP > noiseCHOP > chopexecuteDAT > constantCHOP > selectDAT > mergeCHOP > insertDAT > mergeDAT ...
- Data: parameterCHOP reads parent width/height -> aspect ratio; gridPOP size/columns/rows + cell size = size/(cols-1) via mathCHOPs -> "grid data" null
- Positions: patternCHOP ramp (length = columns, range -sizeX/2..sizeX/2) -> tableDAT of column/row positions (same for rows); fieldPOP mode box to test
- Selector: beatCHOP count as noise seed -> noiseCHOP (1 sample, tiny period) -> chopexecuteDAT: when value crosses 0.5 upward increment constantCHOP row / column
- Random non-repeating integer patternCHOPs (seeded by the row/col counters) give index; select-by-index DATs fetch the chosen position; merge and write as an export table (path, parameter, enable, value) to field1 TX/TY; chop ex...
- Field size per mode (row: size X = grid x2, size Y = cell y; column reversed) via tableDAT + evaluateDAT, transposed, exported to field1 sizeX/sizeY
- (+2 more steps in the JSONL `build_steps`)
- Key params: move speed: 0.005 per frame; noise period: very small for random picks; field size x2: grid size x 2 covers whole row
- Trick: export tables (path, parameter, enable, value) are a compact way to drive many params from DATs
**12. Audio Reactive Visual in TouchDesigner (elburz, 2025-04-25, post 71825, transcript)**
- Ops: circleSOP > transformSOP > copySOP > nullSOP > geometryCOMP > cameraCOMP > lineMAT > renderTOP > transformTOP > audiofileinCHOP > audiodeviceoutCHOP > palette:audioAnalysis > selectCHOP > mathCHOP > lagCHOP > mergeCHOP ...
- circleSOP (divisions 14) + transformSOP, wireframe; duplicate pair into copySOP (input 1 = shapes, input 2 = template points) -> null -> geometryCOMP (RZ = absTime.frame)
- lineMAT white lines, draw points pink with size multiplier up; render 1280x1280; transformTOP black background (alpha 1, comp over)
- audiofileinCHOP -> null "audio in" -> audiodeviceoutCHOP and into palette Audio Analysis; select low, high, snare
- Per band mathCHOP maps 0..1 to a useful range (divisions 6..24 / 8..21; scale 0.25..2 and reversed 2..0.25) then lagCHOP (use different lag values) -> merge -> null "audio react"
- Post: feedbackTOP loop with crossTOP and compositeTOP (feedback level ~0.1); edgeTOP on the feedback so only outlines trail; blurTOP for glow
- Key params: circle divisions: 6..24; scale1: 0.25..2; scale2: 2..0.25 (reversed); render: 1280x1280; threshold: analysis tool threshold lowers sensitivity
- Trick: without lag the parameters snap 8<->21 each beat; add lag per band
**13. Severance Inspired ASCII Text Effect (dcheesman, 2025-03-11, post 71502, chapters)**
- Ops: moviefileinTOP > resolutionTOP > rampTOP > textTOP > replicatorCOMP > texture3dTOP > geometryCOMP > renderTOP > noiseTOP > opticalflowTOP > feedbackTOP > compositeTOP
- Set up variables (0:00)
- Process video input (2:55)
- UV coordinate map (5:48)
- (+7 more steps in the JSONL `build_steps`)
- Trick: replicators + texture arrays = per-instance glyph choice by brightness
**14. Mastering Blob Tracking in TouchDesigner (elburz, 2025-03-05, post 71454, chapters)**
- Ops: blobtrackTOP > kinectazureTOP > thresholdTOP > blurTOP > toptoCHOP > geometryCOMP > feedbackTOP
- Depth sensor choices (3:56)
- Configure tracker (8:56)
- Optimise sensor data (13:27)
- (+7 more steps in the JSONL `build_steps`)
- Trick: prepare/clean the sensor image before Blob Track (threshold, blur, crop)
**15. Intro to POPs: The New Operator Family in TouchDesigner (elburz, 2024-09-18, post 70278, chapters)**
- Ops: pointgeneratorPOP > spherePOP > gridPOP > noisePOP > mathPOP > geometryCOMP > renderTOP
- Attributes and popViewer (0:43)
- Point / vertex / primitive lists (4:14)
- Primitive types (9:55)
- (+3 more steps in the JSONL `build_steps`)
- Trick: POPs were alpha at recording; API names later changed

## Recurring techniques and ops in this slice
- Most-used ops: geometryCOMP (29), feedbackTOP (25), noiseTOP (24), renderTOP (23), levelTOP (20), mathCHOP (16), compositeTOP (16), nullCHOP (15), pbrMAT (15), glslTOP (15), rampTOP (14), blurTOP (14), cameraCOMP (11), lightCOMP (11), baseCOMP (11), moviefileinTOP (11), nullTOP (10), transformTOP (10), audiofileinCHOP (10), displaceTOP (10), selectCHOP (9), bloomTOP (9).
- Palette / external pieces: MediaPipe.tox (5), RayTK (5), RGBDelay (4), audioAnalysis (3), particlesGPU (2), Stoner (1), CantonMapper (1), PerformanceMonitor (1), RGBContrast (1), InteractionOverlay (1), 3DGSToolkit (1), StreamDiffusionTD (1).
- Feedback loop (Feedback TOP + Composite/Transform/Displace/Level, reset with Keyboard In "1") is the base of ~15 looks; always set a TOP colour or 32-bit float to avoid white/ghosting.
- Audio-reactive recipe repeats: Audio File In -> palette Audio Analysis -> Select band -> Math (range) -> Lag -> Null -> parameter (Count of snare = noise seed).
- POP workflow (2025+): Point Generator/Grid > Noise/Random/Attribute POP > Particle POP (own feedback) > Trail POP > Geometry COMP + Line/PBR MAT; Lookup Texture POP for colour; Field POP for spatial masks.
- GLSL porting recipe (Shadertoy): buffers = GLSL TOP + Feedback TOP, `sTD2DInputs[n]`, `TDOutputSwizzle()`, `uniform` on Vectors page, 32-bit float for data buffers, Panel CHOP for mouse.
- Workflow cluster (tekt, function.store, IIHQ): custom parameters over Constant CHOP, OP shortcuts, naming, single source of truth, tox files, cooking/Performance Monitor (Alt+Y).
- Sensors: MediaPipe tox (hand/face, works on Mac), Kinect Azure/Orbbec (Windows), RealSense, WLED/ESP32; Blob Track TOP for floors.

## Top authors
elburz (35), pao.olea (15), tekt (11), Unveil_studio (6), Eusebi (4), dcheesman (4), blankensmithing (3), eric.souther (2), MechBullRodeo (2), marcok06 (1). (`elburz` = The Interactive & Immersive HQ account posting for many presenters: Crystal, Jack DiLaura, Christian, Scott Mann, Marco, Joel, Sal.)

## Flags
- Not in 31550 / third party: sdTOP (post 75505), agentLOP (post 71311), chatLOP (post 71311). SD TOP is a paid custom operator; LOPs (dotsimulate) are a separate toolkit.
- POPs: tutorials 75525, 75535, 75531, 71904, 70278 (alpha in Sep 2024) use the POP family, which exists in 31550; names matched the live build.
- Windows/NVIDIA only: Kinect Azure and Orbbec (71177, 71464, 70998, advanced-kinect), NVIDIA Flex/Flow (70917, 70904), NVIDIA Upscaler/Maxine (71386, 70421), StreamDiffusion (71161), PostShot (3DGS). MediaPipe, WLED, PBR, feedback, GLSL tutorials are fine on Mac.
- Paid / gated files (not downloaded): Patreon project files for Pao Olea, reflekkt (Tracer tox), prismatic (Kinect), Dean Cheesman, elekktronaut tox, Torin Blankensmith clamp-math; Unveil_studio operator (lemonsqueezy). Free: RayTK, MediaPipe plugin (GitHub), project files behind IIHQ email gate. No project files were downloaded in this slice.
- Data quirks: post 71903 embeds an unrelated music video (series is only described on the page); 71011 duplicates 71003; 71311 title/video is a talk on LOPs; posts dated Oct 2026 (75505/75525/75531/75535/75551) are the newest and use the newest POP build.
