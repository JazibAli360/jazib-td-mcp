# Tutorials slice 01 (listing pages 0-5, newest: 23 Oct 2026 back to 24 Feb 2026), 26 Oct 2026

Data: `research_src/tutorials/slice_01.jsonl` (95 entries). Transcripts: `research_src/tutorials/transcripts/<id>.txt` (+ `.vtt`).
Pages 0-5 list 120 rows but only **95 unique tutorials** (the listing shifted while crawling). Op names checked against
`docs/research/ops/INDEX_2025.31550.json` (507 classes). Note: that index has **no device/network I/O ops** (audiodeviceoutCHOP,
keyboardinCHOP, videodeviceinTOP, ndioutTOP, syphonspoutoutTOP, webserverDAT, dmxoutCHOP, oscin/outCHOP, midiinCHOP, ...);
they are standard TD ops, treated as present, not flagged as newer-build.

## Counts
- Tutorials: 95. Videos: 80 YouTube (31 h total), 15 text-only tool/tutorial posts (Aristides.Lab x13, Unveil WEB IS OP, Finger Pinch).
- Category: POP 18, 3D/render 15, camera/interactive 15, ML/AI 12, workflow 8, audio 7, output 4, TOP 3, mapping 3, GLSL 3,
  Python 2, CHOP 2, COMP/UI 2, SOP 1. Relevance 3: 21, 2: 54, 1: 19, 0: 1.
- **Transcripts: 65 of 80 got**; 3 videos have no captions at all (owC0QyOcs5U, XDByG2xAtvU, iFm0Ci1isjU); **12 failed with
  HTTP 429** on the subtitle request (AbszphQ-K64, WJdrnpuYRmI, JKXU66-VYAw, _CsY6lEXy20, f8bH13GcClQ, lPZa2_59UoI, 6V5MHcK_tc8,
  ls7k41ND2UY, XV8w_HJbUaM, V2nJHYzZZrw, eh85YjCSKqk, Xdhze_1lXG4) across 3 passes spaced by 5-min cooldowns (ten agents share one
  IP; metadata dump-json always worked, only the subtitle endpoint was throttled, ~50% of requests). Those 15 entries are built
  from page + chapters + description (marked "inferred" in `teaches`): 75458, 75351, 75267, 75245, 75242, 75213, 75201, 75167,
  75003, 74975, 74966, 74949, 74697, laser-visuals post, 74037. Retry them later with the same yt-dlp line.
- Project files: none downloaded (all are Patreon/paid or GitHub links only; recorded in `files`). Free GitHub: exsstas/SH-in-TD (74796),
  stosumarte/FreenectTD + dcheesman fork (75352, 74384), torinmb/mediapipe-touchdesigner (74152), Alaghast/Voronoi-POP (Linux demo),
  medcelerate/FFGLTouchEngine (75184), Wickedlasers/Laser_OS_TouchDesigner (laser post).

## Top 15 rebuild recipes (full detail in the jsonl)
1. **Audio-reactive sparks, Particle POP** (75525, Joel/IIHQ, 28 min). pointgeneratorPOP (tiny sphere) -> randomPOP (N, size 3, -1..1) ->
   particlePOP (N -> initial velocity, life, birth rate; feedback target = outPOP) -> mathcombinePOP inside loop (age*0.1 = gravity, P.y -= gravity)
   -> trailPOP (match by PartId, short = sparks) -> geometryCOMP + lineMAT (points off, width ~2) + renderTOP. rayPOP onto a boxPOP + noisePOP
   on N for sway. Audio: audiofileinCHOP -> mono -> analyzeCHOP RMS -> lagCHOP -> mathCHOP (0-0.5 -> 50-1000) -> birth rate; snare (palette audio
   analysis) -> countCHOP -> noisePOP seed and box scale. Post: bloomTOP, lookupTOP+rampTOP, hsvadjustTOP, lumablurTOP.
2. **Audio reactivity with basic POPs, Proximity POP lines** (75196). audiofileinCHOP -> mathCHOP mono -> analyzeCHOP(RMS) -> lagCHOP -> speedCHOP
   "evolve" (replaces absTime); kick/snare -> triggerCHOP (attack 0, peak ~0.2). pointgeneratorPOP box surface 1000 pts; attributePOP duplicates P
   as "original"; transformPOP squashes (driven by kick/snare); proximityPOP (max dist 5) makes lines; restore P; deletePOP thins; geometryCOMP+lineMAT
   width 2; feedbackTOP+levelTOP 0.9+addTOP; bloomTOP; lookupTOP ramp.
3. **Edge feedback concert look** (75058, Dean Cheesman). moviefileinTOP -> edgeTOP -> feedbackTOP -> transformTOP scale 1.02 -> blurTOP -> crossTOP
   (input 2 = edge; cross output -> feedback Target TOP) -> addTOP(+edge) -> lookupTOP (rampTOP heat map, extend mirror, ease in/out) -> bloomTOP.
   keyboardinCHOP -> lagCHOP -> bloom pulse and feedback reset; speedCHOP drives ramp phase; second in-line rampTOP keeps darks dark (LED-safe);
   displaceTOP self (mirror, low weight); hsvadjustTOP hue = speedCHOP loop -360..360 speed ~4.
4. **Depth camera installation: filter/zones/spatial buttons** (74384, Orbbec Femto Mega; Mac via network IP). orbbecinTOP (point cloud, depth 512x512,
   colour 1280x720, hw align) -> resolutionTOP half (~230k pts, resize interpolation off) -> toptoPOP (colour input 2) -> transformPOP calibrate.
   Filter: boxPOP + rayPOP(Inside on, scale 0, custom ray attr) -> deletePOP rayinside==0. 3D button: spherePOP + rayPOP -> poptoCHOP/logicCHOP ->
   switchPOP colour. fieldPOP box sweep via lfoCHOP; filterCHOP smooths button; two cameras merged via mergePOP.
5. **POP Lag component** (74702). pointgeneratorPOP -> noisePOP (seed from keyboardin->countCHOP) ; attributePOP duplicates P -> "target"; feedbackPOP +
   mathcombinePOP mix(position, target, 0.1..0.9) with a per-point "blend" attribute from a size-1 noisePOP clamped by limitPOP 0..1; re-init feedback
   after point-count change. Lag = feedback + mix toward stored target (exponential).
6. **Logic-driven particles** (74194). boxPOP+rectanglePOP -> attributePOP colour -> mergePOP; boxPOP tx from lfoCHOP 0.1; noisePOP (output combine none, Curl 3D)
   ; mathmixPOP A>=B on P.x vs 0 -> attribute "emit"; particlePOP 10000, birth attribute = emit, map noise curl -> initial velocity, life 2 s;
   mathmixPOP age/lifespan -> 1-age = "pointscale"; lineMAT near 13 far 29, cameraCOMP tz 17.
7. **DMX with POPs** (74251). gridPOP 8x8 (point prims) -> normalizePOP(P -> "lookup") -> lookuptexturePOP (TOP = rampTOP circular, phase absTime.seconds,
   u/v = lookup0/lookup1, out Color) -> dmxfixturePOP (attr Color.rgb, universe 1, start 1, auto layout) -> dmxoutPOP (sACN, multicast off, device IP).
   Legacy: rampTOP 8x8 -> toptoCHOP -> shuffleCHOP -> mathCHOP 0-255 -> dmxoutCHOP. dmxmapDAT shows channel map. (dmx POP/DAT ops: newer build.)
8. **TouchDesigner + Resolume** (75184, tekt). Final TOP resolution = Resolume comp; syphonspoutoutTOP (sender name `project.name`); in Resolume Sources >
   Syphon (Mac) drag to clip grid. Syphon/Spout shares GPU memory (no latency) vs NDI (compressed, other machine); close the project before opening the next.
9. **Particle collisions with Ray POP** (74455, elekktronaut). pointgeneratorPOP 100k -> particlePOP (1M max, life 5 s) -> transformPOP ty -0.008 ->
   rayPOP (Fast Build ON, input 2 = spherePOP/copyPOP geo) ; limitPOP floor y -0.14; Method 2 uses ray attributes (distance, reflected): mathcombinePOP
   (asterisk keeps all attrs) reflected*|v|*0.05 mixed in when distance<0.01 -> particle velocity. feedbackTOP+levelTOP 0.7+compositeTOP.
10. **Professional project architecture** (75218, tekt). baseCOMP-per-subsystem (sensors, state, render, model, color, output, UI) with operator shortcuts;
   constantCHOP+replaceCHOP so missing hardware still yields channels; info DATs merged in UI; state COMP -> level pulses; RayTK pointMapRender samples
   colour at LED positions; pixel map -> DMX via CHOPs; parameterCOMP panels; test overrides cleared at startup.
11. **Cosmic particles, TOP-as-positions** (74543, pao.olea). addSOP -> convertSOP(particles) -> geometryCOMP instancing from noiseTOP (res via constantCHOP
   256, 32-bit float, mono off, RGB = XYZ, period ~2, harmonics 2-3, translate abs(time.seconds)*0.05); colour noiseTOP->rampTOP lookupTOP; render 1280x1280
   -> levelTOP brightness 1.7 -> hsvadjustTOP -> bloomTOP -> feedbackTOP + edgeTOP.
12. **POP attributes 101** (74641). pointPOP + poptoDAT to inspect; viewer right-click > display attributes (colors/vectors), POP overlays scale; attributePOP
   (lowercase custom names, type float/int/color, 1-4 comps, arrays); mathmixPOP "A" with swizzles (P.x, P.yxz); read-only builtins (_pointindex, bounds, step).
   Capital first letter = Derivative standard attr; Part* from particlePOP, Ray* from rayPOP.
13. **First vertex shader** (74491). phongMAT "output shader" -> glslMAT starter; samplers sTurb/sColor/sNormal; uniforms uXBounds vec2, uLineData vec2;
   vertex: remap world pos -> UV with clamped map(); `TDSimplexNoise(pose)` test then texture lookup; pass `turb` through the vertex struct (same name/order
   in vertex and fragment); fragment `color.rgb += vVert.turb*0.5`; rampTOP 1xN + constantTOP (green) -> mathTOP 0..1 -> -1..1 16-bit float for UV.
14. **Blob tracking 2026** (75167). blobtrackTOP (no 2-blob limit) -> choptoPOP/rectanglePOP per blob -> geometryCOMP+lineMAT; labels, velocity vectors, trails,
   connection lines (transcript missing; chapter-based).
15. **Flip-dot display** (74546, Dean Cheesman). moviefileinTOP -> resolutionTOP (rows 100, width = rows*aspect) -> gridPOP points -> monochromeTOP+thresholdTOP
   -> lookuptexturePOP (UV = texture attr, not P) ; tubePOP disc (columns 20, height ~radius/10) with normalPOP (vertex) + front/back vertex colour attrs;
   copyPOP onto points scale 1/rows*0.45; feedbackPOP mix 0.2 + randomPOP flip; Bayer 2x2 dither; phongMAT, renderTOP.
Honourable: Rolling Tiles (75531: gridPOP + fieldPOP + patternCHOP/DAT index tables + chopexecuteDAT + feedbackPOP/limitPOP loop), 4D rotation with
mathcombinePOP (75380), Trace POP (74774), Projection POP grass (74430), MIDI controls (74032), Window COMP + Perform Mode (74918), cameraViewport (74682).

## Recurring techniques / ops
- Top ops across the slice: renderTOP 41, nullTOP 40, geometryCOMP 40, cameraCOMP 39, nullCHOP 27, lightCOMP 25, mathCHOP 23, rampTOP 22,
  compositeTOP 22, levelTOP 18, bloomTOP 17, lineMAT 15, moviefileinTOP 14, noiseTOP 14, noisePOP 13, feedbackTOP 13, hsvadjustTOP 11.
- **POPs are now the default particle/geometry route** (18 POP tutorials): pointgeneratorPOP/gridPOP -> noisePOP/particlePOP -> mathcombinePOP/mathmixPOP
  attribute logic -> geometryCOMP with lineMAT (points) or pointspriteMAT; rayPOP (collisions, boxes), proximityPOP (lines), trailPOP, feedbackPOP.
- Look finishing recipe: feedbackTOP + levelTOP (0.7-0.9) + addTOP, bloomTOP, lookupTOP with rampTOP palette, hsvadjustTOP hue = speedCHOP loop.
- Audio reactivity: audiofileinCHOP -> mono mathCHOP -> analyzeCHOP RMS -> lagCHOP -> nullCHOP; speedCHOP of level instead of absTime; triggerCHOP for kick/snare.
- Attributes carry state (mathmix A>=B booleans, age/lifespan, birth attribute, map page); lagging = feedback + mix toward a stored "target" attribute.
- Pao Olea series (12) = generative 3D with instancing + PBR + post; RGB-of-a-TOP = XYZ instance positions (needs 32-bit float).
- Interactive: MediaPipe plugin (hand/face/object), Kinect/Orbbec point clouds, blobtrackTOP; output: Syphon to Resolume/MadMapper, DMX via POPs, laser via LaserOS.
- AI: Claude Code + TD MCP/skills (75351, 74828), Gemini toolkit (75108), StreamDiffusion TOP, CoreML/Hugging Face/DINOv3/RF-DETR tox tools (Aristides.Lab, Mac/Apple Silicon).
- Workflow gems (tekt): OP docking, comments/network boxes, TOP viewers (view as points), Info CHOP/DAT, Power Button (stop cooking), Window COMP/Perform mode.

## Top authors
elburz/Interactive & Immersive HQ 34 (Joel, Jack DiLaura, Sal, Christian, Crystal, Ben, ...), Aristides.Lab 15 (Mac ML/sensor tox tools), pao.olea 12,
tekt 12 (RayTK, workflow), dcheesman 5, exsstas 3, audiodevout 3, vtln 2, Unveil_studio 2, elekktronaut 2.

## Newer-build / Windows-only / third-party flags
- Not in our 31550 index (newer-build or unlisted): tracePOP + triangulatePOP (74774), dmxfixturePOP, dmxoutPOP, dmxmapDAT (74251, "2025 series"; verify live with td_list),
  Gaussian-splat POP palette tools (75380). Author builds stated: 74039 = 2025.31550; 74430 says 2025.32460 (projectionPOP exists in ours); 74179 uses 2023.
- Windows-only/NVIDIA: kinectTOP (74420, Windows SDK), nvidiabackgroundTOP (75120), spoutoutTOP (75147; on Mac use Syphon Spout Out TOP).
- Mac-friendly: FreenectTD (Kinect v2), Aristides tox set (CoreML, Kinect 360 POP plugin, PS4 joystickCHOP, TDLidar via iPhone), Orbbec over network IP.
- Third-party/paid: RayTK (free, tekt), MediaPipe plugin (free), SD TOP (paid, Unveil), Pao Olea / Dean Cheesman / Aristides components (Patreon), MadMapper (paid), FFGLTouchEngine.
- Pao Olea wings tutorial: project not for commercial/performance use without permission.
