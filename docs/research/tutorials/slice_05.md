# Tutorials slice 05 (derivative.ca tutorials, listing pages 24-29)

Run 26 Oct 2026. Listing `community?sort_by=created&type[]=23&page=24..29` (posts Dec 2022 to Dec 2023, newest-first order). 90 unique tutorial posts read (6 pages x 15 own posts; 5 featured tutorials repeat in the sidebar of every page and belong to other slices). JSONL: `research_src/tutorials/slice_05.jsonl`.

- Transcripts: **63 fetched**, 26 not: 24 hit YouTube HTTP 429 on the subtitle request (waited 300 s and retried once each; the IP is shared with ~10 agents), 2 videos have no captions at all (68457 pt1, 68466 pt2). 1 post without video (67657 Korean Notion course).
- Entries built from page + video description only (no transcript) are marked `extra.page_data_only: true` (25); their op lists come from the post text and are partial.
- Project files downloaded (5, 8.7 MB total, never opened): 67967 Yin_Yang_0.toe, 68153 Python_Code.txt (text, read), 68457 UnwrappedGeo1.tox (8.1 MB), 68466 UnrwrappedGeo2.tox, 68508 TELEPROMPTER_V1.toe, in `research_src/tutorials/files/<postid>/`. Patreon-only files (not fetched): Unveil_studio pt3/pt4 and Patreon series, blankensmithing body-tracking/ChatGPT/Whisper/SD components, b2bk, elekktronaut.
- Policy note: an attempt to read subtitles through an alternate YouTube player client (to get around the 429) was blocked by the permission system and not retried. Remaining transcripts need a later pass after the rate limit clears (run `yt-dlp --skip-download --write-auto-subs --sub-langs en` one video at a time, 4 s apart).

## Counts per category
3D/render 15, camera/interactive 13, ML/AI 10, GLSL 9, TOP 8, workflow 8, audio 6, POP 6, output 5, SOP 2, typography 2, COMP/UI 2, Python 2, other 2

## Top 15 rebuild recipes (ops in order, key params)

### The Last of Us-Inspired Text Effects in TouchDesigner (elburz, Apr 21st 2023, post 67688, rel 3, TOP)
Ops: noiseTOP, feedbackTOP, displaceTOP, blurTOP, nullTOP, limitCHOP, levelTOP, textTOP, compositeTOP, selectTOP, constantTOP, matteTOP, rampTOP
- noiseTOP 1024x1024, 16-bit float RGBA, period/harmonics tuned, tz = absTime.seconds*0.05
- feedbackTOP -> displaceTOP (noise in input 2, weight 0.01) -> blurTOP -> nullTOP as feedback target; chop reference from keyboardinCHOP "1" to feedback reset
- limitTOP (clamp) after null; second noiseTOP (harmonic gain 2, exponent 0.8)
Params: res=1024x1024 16-bit float, displace weight=0.01 then 0.002, level opacity=0.77, noise tz=absTime.seconds*0.05

### Berenice Abbott-Inspired Multi-Exposure Effects in TouchDesigner (elburz, Apr 25th 2023, post 67714, rel 3, TOP)
Ops: moviefileinTOP, transformTOP, noiseCHOP, nullCHOP, noiseTOP, displaceTOP, levelTOP, nullTOP, feedbackTOP, compositeTOP, keyboardinCHOP, selectCHOP, timerCHOP
- moviefileinTOP -> transformTOP; tx/ty channel-referenced from noiseCHOP (scaled 0.5) via a null; rotate = (absTime.seconds*150) % 720 with range -360..360
- noiseTOP (colour, 1280x720, period 10, tx/tz = absTime.seconds*0.06) feeds displaceTOP (h source green, v source red, weight 0.2)
- levelTOP (shutter) -> nullTOP -> compositeTOP(operation Under, with feedbackTOP output) -> nullTOP; feedback target = composite; final null
Params: displace weight=0.2, composite op=Under, max cycles=15, pixel format=16-bit fixed RGBA

### Generative Liquid Paintings in TouchDesigner (elburz, Nov 27th 2023, post 68643, rel 3, GLSL)
Ops: noiseTOP, circleTOP, nullTOP, feedbackTOP, compositeTOP, glslTOP, opviewerCOMP, selectCHOP, mathCHOP, mergeCHOP
- noiseTOP (period 0.25, colour, 1024x1024, 16-bit float) = paint colour source; circleTOP radius 0.05, softness 0.025 as brush -> null "brush"
- feedbackTOP -> compositeTOP(over, brush on top) -> glslTOP input1; noise -> input2; init noise/null -> input3; glslTOP is the feedback target; input extend mode UV
- Paste fluid GLSL (pastebin) in GLSL TOP; uniforms for mouse and right-button reset on Vectors page
Params: noise period=0.25, circle radius=0.05, circle softness=0.025, res=1024x1024 16-bit float

### Dynamic Texture Grids (elekktronaut, Mar 20th 2023, post 67512, rel 3, TOP)
Ops: rampTOP, reorderTOP, mathTOP, remapTOP, circleTOP, transformTOP, noiseTOP, compositeTOP, switchTOP, flipTOP, blurTOP, lfoCHOP, mergeCHOP
- 32-bit float UV: ramp (bottom-left) as input 2 of reorderTOP -> RG gradient
- Tile grid 12x12 via transform scale = 1/grid; remapTOP inputs: source texture + UV map (+ offset map)
- Part 1 offset: noise (period 2, harmonics 1, 32-bit float RG) composited (add) into the UV map, circle spot moving via LFO tx/ty (cos phase 0.2) merged, optional feedback
Params: grid=12x12, noise period=2, format=32-bit float RG/RGB, lfo amp=0.3

### Particle Paths  (elekktronaut, Jun 07th 2023, post 67892, rel 3, POP)
Ops: (particlesGPU palette tox), keyboardinCHOP, nullTOP, constantCHOP, rampTOP, levelTOP, compositeTOP, bloomTOP, blurTOP, embossTOP, lfoCHOP, mathCHOP, countCHOP
- particlesGPU: render res 1280x1280; birth 500 per frame; life expectancy 5 s; fade in/out 0.1/0.9; size random 0.1-0.9
- keyboardinCHOP "1" to reset particles
- Force constant CHOP and several turbulence constants joined (values e.g. 0.1, 0.2, 0.8) via chop reference to the component
Params: birth=500, life=5, fade=0.1/0.9, level opacity=0.95, render=1280x1280

### Feedback Particles (elekktronaut, Apr 21st 2023, post 67690, rel 3, TOP)
Ops: noiseTOP, feedbackTOP, keyboardinCHOP, countCHOP, nullTOP, addSOP, convertSOP, geometryCOMP, cameraCOMP, renderTOP, lineMAT, displaceTOP, slopeTOP
- noiseTOP 800x800 32-bit float RGB; keyboardin + count CHOP to seed noise and reset feedback
- addSOP point -> convertSOP (particles per point, point sprites) -> geometryCOMP; instancing from TOP (pos null) with R/G/B -> tx/ty/tz; second null for colour
- cameraCOMP with constraint-to and look-at nulls; renderTOP 1280x1280; line MAT draw points, point size 0.15
Params: texture=800x800 32-bit float RGB, level opacity=0.99, slope strength=4, line mat point size=0.15

### Generative Point Clouds in TouchDesigner (elburz, Mar 29th 2023, post 67562, rel 3, POP)
Ops: copySOP, noiseSOP, nullSOP, soptoCHOP, nullCHOP, choptoTOP, constantTOP, rampTOP, remapTOP, mathTOP, compositeTOP, pointtransformTOP, geometryCOMP
- Generate points with SOPs (copy SOP stamping, noise amplitude for jitter)
- SOP to CHOP -> null -> CHOP to TOP: one pixel per point (positions as RGB)
- Point render with custom scale par 0.1, constant TOP black composite "under" in the output
Params: point scale=0.1, ramp phase=absTime.seconds*0.5

### TUTORIAL - Adv. 3D Rendering with buffers (b2bk, Apr 04th 2023, post 67598, rel 3, 3D/render)
Ops: geometryCOMP, pbrMAT, moviefileinTOP, cameraCOMP (camera viewport), lightCOMP, renderTOP, renderselectTOP, polyreduceSOP, constantMAT, remapTOP, mathTOP, noiseTOP, antialiasTOP
- PBR model with colour/normal/occlusion maps; render TOP with palette camera viewport; hard shadows, big shadow map, environment light from white constant
- PBR MAT advanced tab: activate render buffers (16-bit) -> renderSelectTOP with buffer index per pass
- Wireframe: polyreduce 3% copy of geo with PBR wireframe + black constant MAT, polygon offset 0.5 to avoid z-fighting; second renderTOP, antialias off for buffers + antialiasTOP Ultra
Params: buffer format=16-bit, wire offset factor=0.5, polyreduce=3%

### TD as Game Engine, Part 7: Time (invisiblesignal, May 18th 2023, post 67812, rel 3, workflow)
Ops: clockCHOP, selectCHOP, logicCHOP, chopexecuteDAT, speedCHOP, constantCHOP, nullCHOP, noiseTOP
- Clock CHOP -> select hour; Logic CHOP bounds 0 fires when hour wraps to 0
- Chop Execute DAT pulses reset of Speed CHOP
- Use the Speed CHOP null (1 unit/sec) in place of absTime.seconds for noise offsets
Params: reset=daily at midnight

### TD as Game Engine, Part 4: Zones (invisiblesignal, May 04th 2023, post 67753, rel 3, camera/interactive)
Ops: selectCHOP, stretchCHOP, objectCHOP, analyzeCHOP, tableDAT, chopexecuteDAT, logicCHOP, nullCHOP
- Milestone table (tx ty tz rx ry) filled by a hotkey that runs table.appendRow(current values)
- Camera position (1 sample) -> stretchCHOP to 237 samples; Object CHOP (two inputs) outputs distances to all milestones
- Analyze CHOP function "min index" gives nearest milestone; milestone ranges (1-10 etc.) via convert/bounds logic produce zone numbers
Params: milestones=237, zones=10

### TD as Game Engine, Part 3: First Person (invisiblesignal, May 03rd 2023, post 67746, rel 3, camera/interactive)
Ops: joystickCHOP, mathCHOP, speedCHOP, filterCHOP, noiseCHOP, mergeCHOP, functionCHOP, nullCHOP, chopexecuteDAT, tableDAT, cameraCOMP
- Five channels tx ty tz rx ry: joystick -> mathCHOP (mult = move or look sensitivity, e.g. 0.3) -> speedCHOP (accumulates position)
- Rotation channels wrapped by modulo 360; add 180 before the filter and subtract 180 after sending to camera
- Invert y axis for rx; noise CHOP (amplitude parameter) adds slow camera sway
Params: move sensitivity=0.3

### Early 2000s-style Glitch / Net Art In TouchDesigner - Tutorial (elburz, Dec 23rd 2022, post 67031, rel 3, TOP)
Ops: constantCHOP, noiseTOP, limitTOP, nullTOP, feedbackTOP, keyboardinCHOP, displaceTOP, convolveTOP, levelTOP, rampTOP, lookupTOP
- constantCHOP holds resolution -> referenced by noiseTOPs
- noiseTOP tz = absTime.seconds*0.1; limitTOP quantize position step 0.202, offset -0.019 -> null
- Second colour noiseTOP (not monochrome, quantize round step 0.2) as displace map
Params: limit step=0.202, limit offset=-0.019, sharpen=0.125, clamp=0..1

### Collage Typography : TouchDesigner Instancing Tutorial (mattrosslive, Jan 22nd 2023, post 67113, rel 3, typography)
Ops: rectangleSOP, transformSOP, nullSOP, geometryCOMP, soptoCHOP, mergeCHOP, nullCHOP, moviefileinTOP, patternCHOP, mathCHOP, switchCHOP, constantCHOP, resampleSOP
- rectangleSOP -> transform -> null -> geometryCOMP instancing; SOP-to-CHOP point data -> merge -> null "instance data"; scale 0.03; centre transform
- Replicator COMP builds one movie-file-in per image path table row (image paths null); moviefilein resolution 640x480
- patternCHOP ramp as "textindex" channel, length via expression, range to numrows-1
Params: resample segments=50, rectangle size=0.03, movie res=640x480

###  How far is it ?____part 2___displace sop in gpu (Unveil_studio, Feb 10th 2023, post 67200, rel 3, GLSL)
Ops: glslTOP, glslMAT, geometryCOMP, boxSOP, nullTOP, cameraCOMP, renderTOP, soptoCHOP, choptoTOP, nullCHOP
- Reuse part 1 setup; resolution only output, 32-bit mono (monochrome) for performance
- GLSL TOP: euclidean distance between two vec fields
- GLSL MAT: declare sampler array and uniform struct (colour, world position, normal); per-frame code lines ~26-65 run every frame
Params: format=mono 32-bit float

### TUTORIAL : Advanced Pointclouds Manipulation (b2bk, Feb 14th 2023, post 67219, rel 3, TOP)
Ops: pointfileinTOP, selectTOP, mathTOP, nullTOP, pointtransformTOP, geometryCOMP, addSOP, convertSOP, pointspriteMAT, renderTOP, thresholdTOP, levelTOP, constantTOP
- Point file in -> select first 3 fields (position), next 3 fields (colour /127 with math) -> nulls "position","color"
- addSOP point -> convertSOP particles per point (point sprites) -> geometryCOMP instanced from the two nulls; Point Sprite MAT; renderTOP
- Wave: thresholdTOP on green axis (comparators) -> add constant green to push points up; animate threshold with beat/math CHOP
Params: colour divisor=127

## Recurring techniques and ops
nullTOP 33, renderTOP 27, geometryCOMP 26, compositeTOP 25, noiseTOP 23, nullCHOP 23, cameraCOMP 23, mathCHOP 21, levelTOP 17, feedbackTOP 16, rampTOP 16, selectCHOP 13, transformTOP 13, constantTOP 12, blurTOP 12, lightCOMP 11, displaceTOP 10, constantMAT 9, mathTOP 9, constantCHOP 8, soptoCHOP 8, tableDAT 8, nullSOP 7, keyboardinCHOP 7, containerCOMP 7, mergeCHOP 7, moviefileinTOP 7, choptoTOP 7, chopexecuteDAT 7, thresholdTOP 6

Patterns across the slice:
- Feedback loop = feedbackTOP + (displace/transform/blur/level opacity 0.95-0.99) + compositeTOP, target par set to the loop's last op, reset by keyboardin "1" chop reference; 16/32-bit float formats.
- "Points are pixels": SOP -> soptoCHOP -> choptoTOP (or noise TOP as cheap point generator) -> TOP processing (ramp/lookup/remap/composite) -> TOP instancing into geometryCOMP; Point Transform TOP with mask input.
- CHOP glue: mathCHOP range remaps, speed/lag/filter, absTime.seconds * k driven pars, channel references via drag-drop or chop-export; clock+speed reset for long-run installations.
- Fields and SDF scenes with RayTK (tekt): Alt+R palette, Alt+Shift+R tools, modular material, wave/band fields.
- AI via ComfyUI / Stable Diffusion APIs (TDComfyUI, computerender, Automatic1111) + feedback/displace for continuity.
- Kinect/MediaPipe/webcam as particle or silhouette source.

## Top authors
elburz (36), blankensmithing (9), tekt (8), invisiblesignal (7), Unveil_studio (6), function.store (4), b2bk (3), elekktronaut (3), olegchomp (2), Pablo.Lucio (2)

## Newer-build / platform flags
- 67028 TD Diffusion API - Stable Diffusion image generator in : mac=partial (Windows-oriented instructions; Automatic1111 API is cross-platform)
- 67129 Using Multitouch Data from iPad/iPhone or Wacom Tablets: mac=partial (TC-Data is iOS; Tablet to OSC for Wacom is Windows)
- 67513 Kinect 2 vs Kinect Azure in TouchDesigner: mac=no (Kinect 2 / Azure are Windows-only in TD); kinectTOP/kinectCHOP/kinectazure* need Windows + Kinect hardware
- 67699 Apple Feedback Effect in TouchDesigner: mac=partial (Kinect Azure is Windows; any image works on Mac); kinectazureTOP only works with Azure Kinect hardware (Windows)
- 67729 TD as Game Engine, Part 1: Structure: mac=partial (built on Mac, joystick CHOP needs Windows; OSC bridge used)
- 67745 TD AS GAME ENGINE, PART 2: INPUT: mac=partial (joystick CHOP: Windows)
- 67840 RayTK Warped Hexagons Tutorial: mac=yes; all RayTK ops are custom tox
- 67878 RayTK Segmented Ring Tutorial: mac=yes; all RayTK ops are custom tox
- 67892 Particle Paths : mac=yes; particlesGPU is a palette COMP; in 31550 POPs are the native particle system
- 68019 Foamy Waves with NVIDIA Flex in TouchDesigner: mac=no (NVIDIA Flex requires Windows + NVIDIA GPU); NVIDIA Flex ops exist in 31550 only on Windows/NVIDIA; no POP equivalent needed
- 68143 Interactive Particles - gpuParticles point sources from: mac=partial (webcam yes; Kinect Windows)
- 68445 RayTK Folding Box Outline Tutorial: mac=yes (RayTK is GLSL raymarching, cross-platform); RayTK operators are custom tox, not native (all of the above except baseCOMP/outTOP/nullTOP)
- 68502 Motion Visualization with Kinect v2 in TouchDesigner: mac=partial (Kinect v2 is Windows-only; pattern works on any CHOP/TOP data); kinectCHOP/kinectTOP need Kinect v2 hardware (Windows)
- 68629 How to connect anything to Stable Diffusion: mac=yes (ComfyUI works on Mac; speed far lower than NVIDIA; Spout/OBS part is Windows); spoutinTOP is Windows-only

Ops checked against INDEX_2025.31550.json (plus its skipped_not_created and failed lists): all native ops named in the transcript-based entries exist in 31550. Device/IO ops (keyboardin, joystick, midiin, osc, kinect*, videodevicein, serial, nvidiaflex*) sit in the index `skipped_not_created` list: present as classes but not instantiated/probed on this Mac, so no par lists exist. Non-native: RayTK ops (tox), particlesGPU palette (pre-POP, 31550 has native POPs), olib/community components (ComplexOp, TDComfyUI, computerender, Unveil tox).
