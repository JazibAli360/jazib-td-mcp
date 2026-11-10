# Tutorials slice 08 (listing pages 42 to 47), 26 Oct 2026

Source: `derivative.ca/community?sort_by=created&type[]=23&page=42..47` = 120 listing rows, **95 unique tutorial posts** (the newest-first listing shifted between fetches, so rows repeat). Dates: 2020 x49, 2021 x41, Oct 2026 x5. Machine data: `research_src/tutorials/slice_08.jsonl` (one record per post: ops, build_steps, key_params, tricks, recipe, score).

## Counts

Per category: TOP 21, 3D/render 13, workflow 12, GLSL 8, camera/interactive 7, Python 6, SOP 4, audio 4, POP 3, mapping 3, CHOP 3, typography 3, ML/AI 2, other 2, output 2, DAT 1, COMP/UI 1.

Relevance 3: 24, 2: 40, 1: 18, 0: 13. Mac: yes 67, unknown 19, windows-only 8, no 1.

## Transcripts

- Posts with a YouTube video: 91 (86 via the post link, 5 via an embed). **Transcripts fetched: 89** (`research_src/tutorials/transcripts/<id>.txt`, plus the `.vtt` files); metadata (title, channel, duration, views, likes, chapters) for 90.
- Not fetched (6 posts): 8 FaceTrack (blog link only), 13 PAGE Magazine (file only), 17 Kantan Mapper (site link only), 39 French series (playlist link only), 47 Tolch particles (video `KmOE9Mhby8U` is **private**), 50 Tech Pouch (`_SJj4v9kzg8` has no captions). Those use page data only.
- YouTube rate limit: one HTTP 429 on the subtitle endpoint early on (other crawlers share the IP); waited 5 min, retried once, then switched to metadata first and subtitles after. Everything else went through at 4 s spacing, no cookies, no downloads of media.
- Quality caveats: auto-captions are noisy. Several are machine translations of the audio (Arabic for posts 64, 68, 78, 80, 81, 82, 84; Bengali for 28 and 79; Spanish for 1-4, 21, 55, 71, 72; Korean for 31, 66, 67), so values are paraphrased and marked "as heard" in the JSONL. Post 16 caption is song lyrics, 34 and 53 are music tags only, post 26 (Mike Pullan, 2 h interview) has no TD build.

## Files

14 posts carry a free derivative.ca attachment, downloaded (never opened or loaded) to `research_src/tutorials/files/<postid>/`: .toe files 64029, 64050, 64067, 64099, 64008 (generativeartistry.com ports, 4-6 KB each), 64101 (PAGE_MAG_Example.toe 1.8 MB), 63894, 63677, 63654, 63625, 63717 (stepper motor), 63664 (2D vector fields), 63516 (Particles on SDF, 39 KB), 63557 (VHS .toe + jpg). No licence is stated on any of them. Patreon / paid (recorded, not fetched): 64013, 64103, 63943 (Kohui), 63894, 63728, 63664, 63516 (exsstas Patreon files), 75505 (Unveil Studio membership; SD TOP shared tox on GitHub `UnveilStudio/SharedToxs_Unveil_Studio`, not cloned).

## Top 15 as rebuild recipes (ranked by recipe score, then relevance)

### 1. Audio Reactive Particles using TouchDesigner POPs (elburz, Oct 19th 2026, post 75525, score 9)
https://derivative.ca/community-post/tutorial/audio-reactive-particles-using-touchdesigner-pops/75525
Video: 4shfXcXvLDk, 1657 s, mac=yes
- pointgeneratorPOP (small sphere) -> particlePOP (feedback target = inPOP 'end'); randomPOP size 3 attr N range -1..1 before it; particlePOP Map N -> initial velocity
- attributePOP Color orange; tick Color, LineWidth in particlePOP Input attributes
- Inside loop: mathcombinePOP (pre: gravity = age*0.1; P.y = P.y - gravity); particlePOP speed high, birthrate 1000, maxparticles up
- After loop: trailPOP attrmatch PartId, small length -> geometryCOMP with lineMAT (width ~2); randomPOP 1-comp -> LineWidth; rayPOP with box for outward pushes; noisePOP on N
- Render: renderTOP 32-bit float -> lookupTOP(rampTOP) -> bloomTOP -> mathTOP arctan -> hsvadjustTOP -> lumablurTOP masked by circleTOP
- Audio: audiofileinCHOP -> mono -> analyzeCHOP RMS -> lagCHOP -> level -> mathCHOP (0..0.5 -> 50..1000) -> particlePOP birthrate; snare -> countCHOP -> noise seed / noiseCHOP -> lagCHOP -> rayPOP box size

### 2. Fluid Simulation (threedashes, Dec 25th 2020, post 63745, score 9)
https://derivative.ca/community-post/tutorial/fluid-simulation/63745
Video: 2k6H5Qa_fCE, 1690 s, mac=yes
- constantCHOP colorWidth 1280, simulationWidth 128 + aspect 16/9 -> selectCHOP/mathCHOP divide -> 'sizes' (color 1280x720, sim 128x72)
- Splat: constantTOP black 32f at color res -> glslTOP splat (uPoint=mouse -0.8..0.8, uColor 1,0,0, uRadius 0.005, uAspectRatio; out = base + exp-falloff circle*color); velocity splat at sim res with uColor = mouse delta*1000 (32f RG)
- curl glsl: curl=r-l-t+b, out 0.5*curl; vorticity glsl: in velocity+curl, uDelta=absTime.stepSeconds, uVorticity=5; divergence glsl: 0.5*(r-l+t-b); clearPressure glsl: uClear*prev pressure (feedback, keyboardin reset); pressure glsl: (L+R+B+T-div)*0.25
- gradient glsl: vel=vorticity.rg - vec2(R-L,T-B), extend Clamp; advect glsl: coord=uv-delta*vel*texel; out=sample/(1+diffusion*delta) for velocity (0.2) then colour (1)
- Wire velocity and colour through feedbackTOPs; null per stage; final out = advect color; lfoCHOP drives uColor red for hue motion
- Shared neighbour sampling in a textDAT included with #include

### 3. Solar System (Texture Instancing) (elekktronaut, Nov 07th 2020, post 63560, score 9)
https://derivative.ca/community-post/tutorial/solar-system-texture-instancing/63560
Video: ZZlMOWZ7TVk, 2119 s, mac=yes
- geos: sphereSOP>transform (0.1), circleSOP (ZX)>transform for tracks, sun sphere; each into geometryCOMP; cameraCOMP (Look At null, fov ~60) + lightCOMP + renderTOP (rgbkey black)
- constantCHOP>nullCHOP 'val': num_planets 8, speed
- rampTOP (width=num_planets,h=1,32-bit,nearest) > mathTOP range 0.4..2.2 > null 'position' -> planet geo Instance Translate X=r
- noiseTOP (seed) > mathTOP 0.5..1.2 > null 'scale' -> Instance Scale; same for tracks
- rotation: noiseTOP > mathTOP > addTOP+feedbackTOP, limitTOP loop 0..360, * speed > null -> Instance Rotate ry = r
- textures: 5 TOPs each ended in nullTOP named text0..text4; Instance 2 page: textures = text*, index = rampTOP > mathTOP (0..4, Round) > null, channel r
- phongMAT planets, lineMAT tracks, sun = noise>lookupTOP(orange ramp)
- post: lumablurTOP (vertical ramp mask, rot = -cam rz), star noise over, grain noiseTOP

### 4. Trails & Frame Delays in TouchDesigner Tutorial (elburz, Apr 06th 2021, post 64075, score 9)
https://derivative.ca/community-post/tutorial/trails-frame-delays-touchdesigner-tutorial/64075
Video: 6Kj8HFEBcTA, 819 s, mac=yes
- moviefileinTOP -> transformTOP (translate from lfoCHOP->mathCHOP -1..1 to -0.5..0.5; rotate absTime.frame)
- transformTOP -> cacheTOP (cachesize 32)
- cacheselectTOP x6: cachetop = cache, index = me.digits * -5 (copy-paste increments the name digit)
- compositeTOP (Over) of all cacheselects = discrete trail
- RGB split trail: cacheTOP (size 20-30) -> 3 cacheselectTOPs index 0, -10, -20 -> reorderTOP (r from in1, g from in2, b from in3, alpha from in4 optional)

### 5. 2D Collision Detection (elekktronaut, Feb 18th 2021, post 63904, score 8)
https://derivative.ca/community-post/tutorial/2d-collision-detection/63904
Video: n81NAf0Orus, 868 s, mac=yes
- Make two alpha layers (circleTOP polygon shapes) and a mouse object driven by panelCHOP rollu/rollv -> mathCHOP 0..1 to -0.5..0.5 -> circle center.
- In a baseCOMP: inTOP background_objects + inTOP collision_objects -> compositeTOP Multiply.
- -> analyzeTOP (mask alpha) -> limitTOP quantize ceiling step 1.
- -> toptoCHOP (alpha only, name 'collision') -> outCHOP.
- Optional lagCHOP + switchCHOP chosen by custom toggle 'Smooth' with custom float 'Smooth Amount'.
- Use the 0/1 channel (times about 0.4) for the blue channel of the background or in a chopExecute for game logic.

### 6. 3D Shape Subdivisions (elekktronaut, Feb 18th 2021, post 63903, score 8)
https://derivative.ca/community-post/tutorial/3d-shape-subdivisions/63903
Video: CfWXFj0bjto, 1138 s, mac=yes
- boxSOP divisions 20x20x20 -> transformSOP scale 2 -> nullSOP -> soptoCHOP -> nullCHOP 'pos'.
- Small boxSOP + geometryCOMP + cameraCOMP + two lightCOMPs + renderTOP; geo instancing on, translate XYZ = tx ty tz of pos.
- choptoTOP (legacy) -> noiseTOP width = op(...).width (9261), height 1, 32-bit float, mono, period about 6, harmonics 1, translate z absTime.seconds*0.15.
- limitTOP quantize round step 1 -> nullTOP 'scale' -> instance scale XYZ = r.
- phongMAT diffuse 1 specular 0; red and blue lights, soft 2D mapped shadows (softness 0.4, resolution x2).
- Swap input SOP for sphere (poly, freq 20, copySOP 5x at 0.8 scale), superquad or long boxes.

### 7. 3D Texture Tricks in TouchDesigner (elburz, Jan 29th 2021, post 63826, score 8)
https://derivative.ca/community-post/tutorial/3d-texture-tricks-touchdesigner/63826
Video: MB7GkjgxyYI, 982 s, mac=yes
- gridSOP (400 points) -> geometryCOMP with rectangleSOP 1.77x1 inside; Instancing on, Instance OP = grid, TX=P(0) TY=P(1) TZ=P(2)
- moviefileinTOP: Play Mode Specify Index, Index = me.time.frame -> texture3dTOP cache size 100, Prefill on -> nullTOP
- constantMAT Color Map = null; assign as geometry material
- Playhead chain: noiseCHOP (chan 'timer_fraction', 400 samples) -> speedCHOP (speed per sample on, Limit Type Loop; optional constantCHOP/mathCHOP speed scale) -> nullCHOP
- geometryCOMP Instance 2 page: Texture Coordinate OP = null, W = timer_fraction
- Synchronised alternative (all playheads together): timerCHOP 100 frames, cycle on, cycle limit off -> stretchCHOP absolute 0..399 -> W

### 8. 8-Bit Pixel FX in TouchDesigner (elburz, Mar 30th 2021, post 64059, score 8)
https://derivative.ca/community-post/tutorial/8-bit-pixel-fx-touchdesigner/64059
Video: qMlDof42EXo, 576 s, mac=yes
- moviefileinTOP (any clip) -> limitTOP
- limitTOP: Quantize Position = Round, Position Step 0.1 (raise for coarser pixels)
- limitTOP: Quantize Value on, Value Step ~0.1-0.2 for colour banding (optional)
- Optional wash: limitTOP -> blurTOP with large filter size and pre-shrink up
- No resolutionTOPs needed; works at any input resolution at about 0.3 ms CPU

### 9. Circle packing with compute shaders (noones_img, Feb 01st 2021, post 63846, score 8)
https://derivative.ca/community-post/tutorial/circle-packing-compute-shaders/63846
Video: r3aOQMB7qiI, 537 s, mac=unknown
- constantTOP 10x10, all 0, interpolation off, 32-bit float -> feedbackTOP loop (null after glslTOP is the Feedback target; keyboardinCHOP resets)
- glslTOP mode Compute, version 4.3; inputs: 0 = feedback, 1 = noiseTOP mask (10x10 32f, transform = absTime.seconds*0.2), 2 = noiseTOP new positions (10x10 32f, monochrome off, offset 0)
- uniforms: uGrowthRate 0.001, uWidth, uHeight
- per pixel: circle=texelFetch(sTD2DInputs[0]); if circle.a==1 and !edges(circle) and canGrow(circle) circle.b+=uGrowthRate; else if mask>0.5 circle.rg=newPos.rg, circle.a=1
- canGrow loops all texels, skips same r,g, returns false if distance(centres) < r1+r2
- null -> geometryCOMP instancing: translate OP R,G=XY; scale OP B; circleSOP NURBS curve; wireframeMAT or constantMAT with rampTOP colour; renderTOP black bg alpha 1

### 10. Drawing with particles (noones_img, Nov 19th 2020, post 63611, score 8)
https://derivative.ca/community-post/tutorial/drawing-particles/63611
Video: hZRZqBKLoUg, 215 s, mac=yes
- addSOP -> convertSOP (particles per point) -> geometryCOMP (Instancing on, translate OP = null, tx=r, ty=g); orthographic cameraCOMP; renderTOP; constantMAT
- glslTOP: fragColor = vec4(vUV.st,0,1); noiseTOP (res = glsl, 32-bit float, mono off, amp 0.07, exp 135, translate = absTime.seconds*0.2) -> compositeTOP Add with UV
- feedbackTOP + crossTOP (0.01) loop: cross input1 = feedback, input2 = composite; feedback target = cross; nullTOP; keyboardinCHOP resets
- Image: moviefileinTOP -> fitTOP (res = glsl, Fit Outside) -> nullTOP -> geo instance Color OP (r,g,b)
- reorderTOP alpha=colour -> geo Instance Active = alpha
- Trails: feedbackTOP + compositeTOP over render, levelTOP low opacity

### 11. Easy Feature Tracking with Script TOP and OpenCV in TouchDesigner - Tutorial (elburz, Dec 06th 2020, post 63688, score 8)
https://derivative.ca/community-post/tutorial/easy-feature-tracking-script-top-and-opencv-touchdesigner-tutorial/63688
Video: 1Uw2PWTR_XM, 938 s, mac=yes
- videodeviceinTOP -> fitTOP (half res) -> nullTOP 'null1' -> scriptTOP
- scriptTOP onCook: import numpy as np; import cv2
- image = op('null1').numpyArray(delayed=True)
- gray = np.float32(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY))
- dst = cv2.dilate(cv2.cornerHarris(gray, <args from OpenCV doc example>), None)
- image[dst > 0.01*dst.max()] = [0,0,1,1]   # RGBA, 0-1
- scriptOp.copyNumpyArray(image)
- Keep resolution low (640x360) for real-time

### 12. Easy Person Detection with Blob Tracking (elburz, Jan 30th 2021, post 63832, score 8)
https://derivative.ca/community-post/tutorial/easy-person-detection-blob-tracking/63832
Video: ZplOrM6G6JI, 825 s, mac=yes
- videodeviceinTOP (or NDI in) -> nullTOP 'background' (lock it while the scene is empty)
- blobtrackTOP: input 1 = live video, input 2 = locked null; Delete Overlapping Blobs on, Delete Nearby Blobs on, Max Blob Size high, Min Blob Size raised until only the person blob stays
- constantCHOP chan 'detection' = op('blobtrack1_blobs').numRows
- filterCHOP (width 1-3) -> logicCHOP (Off When Outside Bounds, lower 2 (or 1.1-1.5 with filter), upper 999) -> nullCHOP 'present'
- Optional: timerCHOP while empty -> unlock/lock the null for a fresh background

### 13. Extracting Data from Featuring Tracking in TouchDesigner (elburz, Dec 10th 2020, post 63692, score 8)
https://derivative.ca/community-post/tutorial/extracting-data-featuring-tracking-touchdesigner/63692
Video: c-Sx1xo9sYQ, 1443 s, mac=yes
- ndiinTOP/videodevicein -> fitTOP (low res) -> nullTOP 'null1' -> scriptTOP 'script1'
- script1 onCook: image=op('null1').numpyArray(delayed=True); run OpenCV subpixel-corner example producing 'corners' (N x 2 float array); scriptOp.store('corners', corners); scriptOp.copyNumpyArray(image) (RGBA, 0-1)
- scriptCHOP 'script2' onCook: scriptOp.clear(); c=op('script1').fetch('corners'); tx=scriptOp.appendChan('tx'); ty=scriptOp.appendChan('ty'); scriptOp.numSamples=len(c); loop i: tx[i]=c[i][0]; ty[i]=c[i][1]
- Alt: tableDAT clear + appendRow(i) per corner -> dattoCHOP (Channel per Column, first row/col = Values)
- mathCHOP to rescale to full resolution

### 14. Generative Geometric Design in TouchDesigner (elburz, Nov 07th 2020, post 63563, score 8)
https://derivative.ca/community-post/tutorial/generative-geometric-design-touchdesigner/63563
Video: coS_lvjnD4w, 1245 s, mac=yes
- circleSOP -> geometryCOMP (via right-click > COMP > geometry) with lineMAT
- circleSOP #2 -> nullSOP; geo Instance page: on, translate OP = that nullSOP, TX/TY/TZ = P(0) P(1) P(2)
- transformSOP in front of the null: ry = absTime.seconds*k for rotation
- noiseCHOP: channel 'scale', units Samples 0..39 -> mathCHOP (range -1..1 -> 0.5..1.25) -> nullCHOP -> geo Instance Scale X/Y/Z
- noiseCHOP transform tz = absTime.seconds*3
- Swap in patternCHOP (sine, length 40, name 'scale', phase absTime.frame*0.01) by dropping it on the existing wire
- Change source: rectangleSOP 2.5x2.5, boxSOP, or sphereSOP (722 pts); set CHOP length = op('null1').numPoints (noise end = numPoints-1)
- lineMAT: line width vs camera distance for depth

### 15. Liquid paint marbling Effect in Touchdesigner (Kohui, Mar 20th 2021, post 64013, score 8)
https://derivative.ca/community-post/tutorial/liquid-paint-marbling-effect-touchdesigner/64013
Video: w4DXtVWdlYg, 1089 s, mac=yes
- noiseTOP A (1000x1000, period 2, mono off, 32-bit float) -> transform (translate z absTime.seconds*0.1)
- noiseTOP B (second seed, mono off, 32-bit float) as displace source
- feedbackTOP -> displaceTOP (source = noise B, weight very low) ; set feedbackTOP target to the displace output; press Reset
- For image sources: infoCHOP res x/y ratio -> displace weight y = weight x * ratio
- Optional: slopeTOP+blurTOP of the source composited average with the noise
- Video: moviefileinTOP composite (maximum) with feedback, levelTOP opacity <1 in the loop, displace weight 0.1

## Recurring ops (posts using each, across all 95)

nullTOP 42, geometryCOMP 34, noiseTOP 31, renderTOP 29, mathCHOP 29, cameraCOMP 29, compositeTOP 28, nullCHOP 28, feedbackTOP 21, rampTOP 21, constantCHOP 19, constantMAT 19, transformTOP 17, selectCHOP 16, moviefileinTOP 16, levelTOP 14, constantTOP 14, mergeCHOP 12, lookupTOP 12, displaceTOP 12, glslTOP 12, blurTOP 11, keyboardinCHOP 11, lineMAT 10, gridSOP 10, mathTOP 10, patternCHOP 9, countCHOP 9, limitTOP 9, lfoCHOP 9, circleSOP 9, transformSOP 9, rectangleSOP 8, noiseCHOP 8, lagCHOP 8, lightCOMP 8, circleTOP 8, soptoCHOP 7, layoutTOP 7, switchTOP 7.

## Recurring techniques

- **Feedback + instancing as the core of 2020-21 generative work** (noones_img, elekktronaut): feedbackTOP/cacheTOP trails, TOP-as-instance-data (position/colour/scale from noise/ramp/movie textures via `geometryCOMP` instancing), point-file / UV-grid driven instances.
- **GLSL TOP for solvers**: fluid (Stam), Lorenz attractor, circle packing (compute), reaction-diffusion, 2D vector-field particles; 32-bit float TOPs and 1x1 / 1-pixel-high TOPs as data containers.
- **Lookup/ramp colouring** (lookupTOP + rampTOP), `me.digits` copy-paste index tricks for cache selects, Cache TOP delays, Script TOP + OpenCV (numpy arrays), Blob Track TOP, Table DAT <-> CHOP data bridges.
- **Interactive input**: Kinect (Windows only), ZigSim / iPhone ARKit depth over OSC/NDI, Script TOP feature tracking, MIDI keyboard visualisation, mouse-driven instances.
- **Workflow / ops**: Perform DAT, Op Find DAT, Python string hacks, 2026 timecode features, Notch blocks, OBS.Ninja, cloud (Paperspace), Arduino stepper over serial, three.js round trip.
- **POPs (2026 posts)**: particlePOP + feedbackPOP loop, rayPOP, noisePOP, attributePOP, audio-reactive birth rate; Rolling Tiles (POPs + CHOPs + DATs). These are the only native POP tutorials in this slice.

## Top authors

elburz 33, noones_img 16, elekktronaut 8, internetbigboi 5, tekt 5, exsstas 3, Akenbak 3, tolch 2. elburz = The Interactive & Immersive HQ (broad workflow + production), noones_img = 1-4 minute shader/TOP recipes, elekktronaut = Kohui-style generative/instancing walk-throughs, tekt = RayTK, internetbigboi / Akenbak = Spanish-language series.

## Newer-build / not-in-our-index / Windows-only flags

- `INDEX_2025.31550.json` is **incomplete** (e.g. no `keyboardinCHOP`, `mouseinCHOP`, `midiinCHOP`, `oscinCHOP`, `oscoutCHOP`, `ndiinTOP`, `videodeviceinTOP`, `audiodeviceoutCHOP`, `midiinmapCHOP`, `multitouchinDAT`, `serialDAT`); all are standard TD ops that exist in real builds, so treat them as index gaps (verify live with `td_create` before relying on them). Agents flagged them in `ops_not_in_31550` with that note.
- Genuinely not native: RayTK (posts 14, 32, 48, 62, 63; community toolkit), Kantan Mapper (17), SD TOP (16, third-party C++ op, Patreon), Palette tools (`particlesGpu`, `opticalflow`, Audio Analysis), FaceTrack SOP/CHOP (8, NVIDIA AR SDK).
- Windows-only / needs hardware: Kinect posts (27, 30, 57), NVIDIA FaceTrack (8), Notch blocks (49, 58, 76, 88), Paperspace cloud VM (59). Post 38 (circle packing) needs GLSL 4.3 compute: untested under our Vulkan/MoltenVK build.

## Open questions

- Verify the 5 Lorenz constants (heard as "10 20 3/8", likely sigma 10, rho 28, beta 8/3) and other garbled values flagged "as heard" before rebuilding.
