# Tutorials slice 07 (listing pages 36-41, 26 Oct 2026)

Source: `derivative.ca/community?sort_by=created&type[]=23&page=36..41`. 90 tutorial posts (15 new per page; the first 5 links on every page are the same pinned newest posts 75505-75551, owned by the newest-pages slice and skipped here). Posts date Aug 2020 to Jan 2022 (86 from 2021), so the builds are 2020-2021 era TouchDesigner: parameter names are mostly stable, but check ops against the 31550 index before use. Data: `research_src/tutorials/slice_07.jsonl` (one record per post: ops, build_steps, key_params, tricks, files, mac flag).

## Counts
- Posts read: 90 of 90. Videos: 93 (YouTube). 5 posts have no video: 65664 Medium article, 64941 article, 64891 GitHub link, 65571 mp4 asset, 65237 course announcement. 65246 (Boids) is Vimeo only and login-gated, skipped.
- Transcripts fetched: 86 of 93 videos (VTT + plain `.txt` in `research_src/tutorials/transcripts/`). Failed: 7, all because YouTube has no captions (Ub9oDIi-VLE, Vs_3N85Y6nQ day-1 stream, jVZW2Cte-IE, 43wJGUex75w, l1ZlwbHuhrU, Mow-z0Nt_4o, SCQrykjtEpo). Unreliable: wJ6AaBfy3-0 (auto-captions detected as Vietnamese on English audio).
- YouTube 429 hit twice on subtitle downloads (the first run used `en.*` and pulled many translated tracks). Fixed by asking for one track only (`en-orig` or the video language `*-orig`), 5 minute pause, retry: all 14 retried captions then succeeded.
- Non-English: Spanish x3 (8Gik4023y_Y, vN2Ec4pPS4k, QUBSNq1JT2c), Korean x6, Japanese x1, Persian x2, Chinese x1; steps for the ASR-noisy Korean ones are approximate (low confidence, flagged in the record).
- Categories: TOP 16, 3D/render 15, camera/interactive 9, SOP 9, audio 7, GLSL 6, workflow 5, ML/AI 4, Python 4, output 4, mapping 4, COMP/UI 3, POP 3, DAT 1
- Relevance (general TD mastery): 3 = 39, 2 = 32, 1 = 19.
- Files downloaded (never opened): 6 free `.toe/.tox`, 123 KB total, in `research_src/tutorials/files/<postid>/`: 65617 matrix-cube-tutorial-01.3.toe, 65194 pixelnoisetutorial1.1.toe, 65176 "2D vector fields 2 - public.toe", 65174 ReaRouteTD_MONO_1_4.tox, 65038 srt_in_example_TD.toe, 64888 "Glitches - free version.toe". Skipped: 65571 VIDEO1.mp4 (not a TD file type). Patreon/paid or Drive (not fetched): elekktronaut, noones_img, Unveil, factorysettings, blankensmithing, notothetalkingball (free via Patreon). exsstas moved his Patreon files to GitHub (exsstas/TD-tutorials), linked in 65176 and 64888.

## Top 15 as rebuild recipes

1. **Interactive Feedback Painting in TouchDesigner Tutorial** (elburz, 65576, 16 min, 2021-11 (build unknown)). Ops: circleTOP, constantTOP, noiseCHOP, mathCHOP, nullCHOP, compositeTOP, feedbackTOP, levelTOP, blurTOP, transformTOP, lookupTOP, rampTOP, nullTOP, limitTOP.
   Params: level opacity=0.9; transform scale=1.01; timeslice=on; circle radius=0.1-0.4
   - constantTOP background 1920x1080; circleTOP; compositeTOP Over (transform circle in comp)
   - noiseCHOP time-sliced, math -1..1 -> -0.5..0.5, null as test position
   - feedbackTOP from composite; loop: feedback -> blur -> transform (scale 1.01) -> level (opacity 0.9) -> back into composite
   Trick: time-sliced noise CHOP = quick moving test data

2. **Recursive growth with feedback** (noones_img, 65216, 4 min, 2021-09 (build unknown)). Ops: noiseTOP, thresholdTOP, feedbackTOP, keyboardinDAT, blurTOP, compositeTOP, levelTOP, mathTOP.
   Params: threshold A=0.7; threshold B=0.4; level brightness=2; math multiply=0.98
   - noiseTOP 32-bit float, higher res; thresholdTOP 1.0 -> white seeds (offset/period change size/count)
   - feedbackTOP with keyboardinDAT as reset
   - branch A: threshold 0.7 -> blur; branch B: blur (large) -> threshold 0.4; compositeTOP subtract; levelTOP brightness 2
   Trick: 32-bit float is essential

3. **5-minute Kaleidoscope in TouchDesigner** (elburz, 65437, 14 min, 2021-10 (build unknown)). Ops: tileTOP, mirrorTOP, lfoCHOP, mathCHOP, nullCHOP, moviefileinTOP, compositeTOP.
   Params: lfo frequency=0.005; math to range=0-360; tile=2x2
   - source (movie) -> tileTOP 2x2 with flip x/y and overlap U/V to blend
   - -> mirrorTOP (choose mirror axis)
   - lfoCHOP frequency 0.005 -> mathCHOP from -1..1 to 0..360 -> null -> reference mirror rotation
   Trick: overlap U/V blends tiles for the "smeared" kaleidoscope look

4. **Fractals Tutorial** (elekktronaut, 64861, 8 min, 2021-05 (build unknown)). Ops: noiseTOP, nullTOP, feedbackTOP, keyboardinCHOP, compositeTOP, transformTOP, levelTOP.
   Params: noise period=2-3; noise amplitude=0.12; composite ops=overlay + average
   - noiseTOP 1920x1080 32-bit float rgb, period 2-3, harmonics 1, amplitude 0.12; transform phase absTime.seconds*0.1; null "bg"
   - feedbackTOP + keyboardin reset
   - compositeTOP A overlay (noise over feedback), compositeTOP B average; input ORDER matters
   Trick: input order of the composites is critical

5. **Easy Slitscan in TouchDesigner Tutorial** (elburz, 65586, 8 min, 2021-11 (build unknown)). Ops: videodeviceinTOP, texture3dTOP, timemachineTOP, rampTOP, noiseTOP, nullTOP.
   Params: cache size=32 -> 320; black offset=-320; ramp pixel format=32-bit RGBA
   - camera/movie -> texture3dTOP (cache size 32 default; try 320 at 1280x720)
   - timemachineTOP: input 1 = texture 3D, input 2 = rampTOP; ramp pixel format 32-bit RGBA for smooth gradation
   - timemachine black offset = -(cache size) so darkest = oldest frame
   Trick: Texture 3D TOP shows all frames at once; cache TOP needs cache selects

6. **Make Anything Audio Reactive** (elekktronaut, 64122, 32 min, 2021-04 (build unknown)). Ops: audiodeviceinCHOP, audiofileinCHOP, audiospectrumCHOP, envelopeCHOP, mathCHOP, beatCHOP, triggerCHOP, logicCHOP, nullCHOP, circleTOP, noiseTOP, switchTOP, levelTOP, displaceTOP.
   Params: envelope width=10; trigger attack/release=0.2/0.2 s; feedback weight=0.998
   - audio setup: select/average channels; envelope CHOP + math (combine divide, envelope width 10) = normalised level; audio analysis tool for kick/snare/hat channels
   - beat CHOP at tempo (e.g. 120) for counters/pulses; trigger CHOP attack/release 0.2 s; logic CHOP toggle
   - channel -> null -> export/reference to circle radius, noise amplitude/period/phase, switch index, level/opacity, displace weight
   Trick: the same pattern (analysis -> null -> reference) drives anything

7. **Easy Swipe Detection in TouchDesigner** (elburz, 65333, 15 min, 2021-09 (build unknown)). Ops: containerCOMP, panelCHOP, selectCHOP, slopeCHOP, mathCHOP, logicCHOP, trailCHOP, mergeCHOP, nullCHOP.
   Params: swipe threshold=7 to 20; container=400x400
   - containerCOMP 400x400; panelCHOP with component overridden to the container (it looks at its parent otherwise)
   - selectCHOP insideu insidev; slopeCHOP -> speed
   - selectCHOP the "select" (click) channel and mathCHOP multiply to zero spikes on click
   Trick: use insideu/insidev not u/v (u/v snaps on click)

8. **Catching Errors in TouchDesigner** (elburz, 65426, 14 min, 2021-10 (build unknown)). Ops: errorDAT, moviefileinTOP, textDAT, compositeTOP, containerCOMP.
   Params: errorDAT source=path to subtree
   - errorDAT: Source = path (e.g. /project1/container1) to log only a subtree
   - generate errors (bad movie path, python script error, composite missing inputs) to see table columns
   - errorDAT callback in Python: on a movie load error set op(source).par.file to a fallback asset (e.g. Count123.mov)
   Trick: same message text as the middle-click error popup

9. **2-Line GLSL Point Cloud Clipping in TouchDesigner** (elburz, 65420, 16 min, 2021-10 (build unknown)). Ops: pointfileinTOP, glslTOP, nullTOP.
   Params: uniform type=vec2 per axis
   - pointfileinTOP as source (or any XYZ-in-RGB texture)
   - glslTOP: Vectors page add 3 uniforms vec2 (uXClip, uYClip, uZClip) as parameter pairs; names must match code
   - shader: vec4 color = texture(sTD2DInputs[0], vUV.st); if(color.r<uXClip.x || color.r>uXClip.y){color=vec4(0.0);} repeat for g (y) and b (z); fragColor = TDOutputSwizzle(~
   Trick: replace float with vec2 uniforms to hold min and max in one parameter

10. **Basic particle system with GLSL Top** (noones_img, 64910, 9 min, 2021-06 (build unknown)). Ops: addSOP, convertSOP, geometryCOMP, cameraCOMP, constantMAT, renderTOP, constantTOP, feedbackTOP, keyboardinCHOP, glslmultiTOP, renderselectTOP, noiseTOP, reorderTOP, compositeTOP.
   Params: resolution=100x100; step=1/60; noise=4D simplex, animate 4th dim with absTime.seconds
   - add SOP points -> convert (particles per point) -> geo with constantMAT, camera, renderTOP
   - constantTOP black = initial position; feedbackTOP holds current position; keyboardinCHOP resets feedback
   - glslmultiTOP: GLSL version 4.3, compute shader mode, 2 colour buffers (0 = pos, 1 = velocity); renderSelectTOPs pick index 0/1
   Trick: 32-bit float for negative values

11. **GLSL particles with 2D velocity fields** (noones_img, 65008, 7 min, 2021-07 (build unknown)). Ops: addSOP, convertSOP, geometryCOMP, cameraCOMP, constantMAT, renderTOP, glslTOP, mathTOP, nullTOP, feedbackTOP, keyboardinCHOP, noiseTOP, slopeTOP, reorderTOP.
   Params: grid=100x100; dt=1/60; lifespan=offset 2 amp 0.5
   - add SOP (points) -> convert (particles per point); geo + camera + constant MAT + render
   - glslTOP grid: use vUV.st in rg, blue 0, 32-bit float; math range 0..1 -> -1..1; null "ini pos"
   - feedbackTOP (target = glsl output); geo instancing translate rgb from the feedback null (res 100x100)
   Trick: 32-bit float for negative coordinates

12. **Interactive Particles & Metaballs in TouchDesigner** (elburz, 65446, 12 min, 2021-11 (build unknown)). Ops: gridSOP, sortSOP, pointSOP, particleSOP, metaballSOP, forceSOP, transformSOP, mouseinCHOP, mathCHOP, nullCHOP, nullSOP, geometryCOMP, boxSOP.
   Params: force=+-0.3; box size=0.01; grid=50x50
   - gridSOP 50x50 -> sortSOP random -> pointSOP (scale 0.01) -> particleSOP input 1; birth more particles
   - metaballSOP -> forceSOP (force 0.3 attract, -0.3 repel) -> transformSOP -> particle input 3; enable compare flag on the force
   - mouseinCHOP normalised -> math range to the bounds (-5..5) -> null, reference transform tx/ty
   Trick: metaball is a force field, not geometry

13. **Push Pin Effect Breakdown in TouchDesigner** (elburz, 64945, 17 min, 2021-06 (build unknown)). Ops: gridSOP, nullSOP, geometryCOMP, boxSOP, rectangleTOP, noiseTOP, fitTOP, mathTOP, nullTOP.
   Params: grid=20x20 then 50x50; math range=0..10
   - gridSOP 20x20 -> null SOP; inside geometryCOMP delete torus, instance source = null SOP, translate = P(0),P(1),P(2)
   - source texture resolution must equal point count (rows*cols): fit TOP / noise res 20x20; middle-click shows count mismatch
   - set pixel format 32-bit float on every TOP in the chain (8-bit gives steps)
   Trick: mismatch between instance count and texture size is the common error

14. **The Best Communication Protocols in TouchDesigner** (elburz, 64840, 17 min, 2021-04). Ops: touchinTOP, touchoutTOP, ndiinTOP, ndioutTOP, spoutinTOP, spoutoutTOP, syphonspoutinTOP, oscinCHOP, oscoutCHOP, touchinDAT, touchoutDAT, soptoCHOP, choptoTOP.
   Params: touch out codec=uncompressed for data textures
   - TOP same computer: Spout (Win) / Syphon (Mac)
   - TOP across machines: NDI (compressed) or Touch In/Out TOP with uncompressed codec for exact data
   - CHOP: OSC or Touch In/Out CHOP
   Trick: NDI compression warps data textures: use uncompressed Touch Out for point clouds

15. **Anaconda (Miniconda)** (JetXS, 64941, article, article updated 2024-11; obs). Ops: executeDAT, textDAT.
   Params: none stated
   - install Miniconda; check Python version via Alt+T textport
   - conda create -n td-demo python=3.11; conda activate; conda install/pip install packages
   - in TD, add env paths to sys.path/os.environ before importing
   Trick: do not swap NumPy/OpenCV versions that ship with TD

Also strong, see jsonl: 65117 abstract 3D sculpture (600x600 noise-TOP instancing, elekktronaut #43), 65079 circuit bending (feedback + displace glitch), 64888 glitch/pixel sort/datamosh (Cache + Time Machine), 65012 texture slicing, 64807 alpha matte with Channel Mix, 64850 drag and drop callbacks, 64796 Xbox controller camera, 64897 GeoPix LED mapping pipeline, 64866 projection mapping tool tour, 64121 endless instanced world.

## Recurring techniques and ops
- Most-used ops across the slice: geometryCOMP 36, renderTOP 27, noiseTOP 25, nullTOP 23, nullCHOP 22, mathCHOP 22, cameraCOMP 22, rampTOP 21, compositeTOP 20, feedbackTOP 19, selectCHOP 14, levelTOP 14, blurTOP 13, mathTOP 12, constantMAT 11, transformTOP 11, constantCHOP 9, boxSOP 9.
- **TOP-instancing as data pipeline** (~20 posts): noise/ramp/chop-to-TOP textures as per-instance translate/rotate/scale/colour; rules: texture resolution must equal instance count, and every TOP in the chain must be 32-bit float (8-bit gives 255 steps and no negatives).
- **Feedback TOP loops** (19): feedback -> blur/level/transform -> composite over; reset with a keyboard-in CHOP; Displace TOP inside the loop; values must be tiny; Lookup TOP + Ramp for colour.
- **Texture 3D TOP + Time Machine TOP** (7): frame cache on the GPU (slitscan, light trails, 400 independent movie playheads, datamosh). Watch VRAM.
- **GPU particles in TOPs** (6): feedback + GLSL TOP/GLSL Multi TOP, position+life per pixel, velocity fields; geometry-comp instancing reads the position TOP. Compute-shader versions (GLSL Multi, GLSL 4.3) carry a Mac warning from the author; test on our Vulkan build.
- **CHOP glue**: select -> math (range) -> lag/filter -> null, then chop-reference into parameters; Speed CHOP as integrator; Logic/Trigger for thresholds; chopexecute DAT for stepped events; Panel CHOP for UI gestures.
- **Audio-reactive**: envelope math trick, beat CHOP, trigger CHOP; the pattern analysis -> null -> parameter reference drives any parameter (64122, 65638).
- **Mapping/output**: Kantan Mapper (2D) and Camschnappr (3D), measured-aspect virtual screens, EDID spoofing (Quadro), protocol choice (Spout/Syphon same machine, NDI or Touch In/Out TOP between machines, uncompressed codec for data textures).
- Habit across authors: always drop a **null** on each output you will reference; set resolution to parent panel size; one constant CHOP as the settings hub.

## Top authors
- elburz 35, Unveil_studio 7, noones_img 7, elekktronaut 7, tekt 4, DavidBraun 2, uisato 2, internetbigboi 2, tormozgh 2, exsstas 2. elburz = The Interactive & Immersive HQ (Elburz, Jack DiLaura, Crystal Jow guests): clear 8-17 min recipes, best for rebuilds. elekktronaut (Bileam Tschepe) and noones_img: dense short technique videos. tekt = RayTK (raymarching toolkit, third party).

## Newer-build / Windows-only / third-party flags
- **Not in our 31550 ops index** (see `ops_not_in_31550` + `_reason` per record): 29 RayTK entries (3rd-party toolkit, 4 posts), 20 Windows/NVIDIA/hardware-only (Kinect Azure/V2 x6 posts, Nvidia Flex/Denoise/Background x5, Face Track CHOP x2, Leap Motion), 6 palette components (Kantan Mapper, Camschnappr, GPU Particles, 2D slider, TDAbleton), 2 ChucK custom operators. 50 more are normal I/O or network ops (Keyboard In, Mouse In, Video Device In, Audio Device In/Out, OSC, NDI, Spout/Syphon, Touch In/Out, Serial, Joystick, MIDI Out, Web Browser) that exist in TD but are missing from the shipped index file: a gap in `INDEX_2025.31550.json`, not in TD.
- **Windows/NVIDIA only (no Mac)**: 65625, 65619 (Kinect Azure), 65033, 65006 (Kinect V2), 65172, 65161, 65104, 65078 (RTX), 65100, 65071 (Flex), 65017 (Quadro EDID), 65294/65160 (Unreal + Spout).
- **Version caveats**: 64941 Anaconda article says it is obsolete from builds 2025.30000+; use the palette TDPyEnvManager (post 72024). 65180 shows Python 3.7-era paths; 31550 ships a newer Python. RayTK videos 64131 are flagged OUTDATED by the author, and RayTK is now bundled differently. Tutorials date from 2020-2021 builds, so Mac/Vulkan behaviour of compute shaders (64910, 64948, 65246) is untested.
- **Mismatch**: 65353 is titled "Easy optimization tricks" but links the 3D-texture tricks video (IIHQ #031); recorded as the video really is.

## Open questions
- Do GLSL Multi TOP compute shaders (64910/64948/65246 boids) run on 31550 macOS Vulkan? Probe before relying on them.
- Vimeo videos (65246 Boids walkthrough, 65624 ChucKDesigner) need a login for yt-dlp and oEmbed 404s: skipped by rule; ChucKDesigner has YouTube equivalents (captured).
- The shipped ops index misses I/O ops; regenerate it from a live `td_exec` class listing so recipes can be checked end to end.
