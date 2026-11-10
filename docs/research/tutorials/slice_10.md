# Tutorials slice 10 (listing pages 54-58): the oldest community tutorials

Scraped 26 Oct 2026 for TD 2025.31550 (macOS). Data: `research_src/tutorials/slice_10.jsonl` (78 records, one per post). Transcripts: `research_src/tutorials/transcripts/<videoid>.txt`. Project files: `research_src/tutorials/files/<postid>/`.

Note: pages 54-58 hold 73 posts from Oct 2019 - Apr 2020 plus 5 very recent ones (Oct 2026: 75505, 75525, 75531, 75535, 75551) that the 'created' sort puts here. 62215/62677/62229 etc. are real posts; one post URL (62677) has no id in its slug.

## Counts
- Posts read: 78. Videos: 59 YouTube embeds with a usable transcript, 16 YouTube embeds without one, 12 Vimeo (page text only: Vimeo captions need a login).
- Category: workflow 11, 3D/render 11, camera/interactive 11, TOP 9, audio 7, SOP 5, GLSL 5, Python 4, typography 3, POP 3, output 2, CHOP 2, mapping 2, ML/AI 2, COMP/UI 1
- Relevance (0-3): 3: 28, 2: 32, 1: 14, 0: 4
- Transcripts fetched: 59 of 75 YouTube ids (EN captions for ~40, ES auto-captions for ~19; Spanish ones translated in the records). Failed/empty: 7-7L3JqUcUw (video unavailable); music-only/no speech: QUBSNq1JT2c, Ito-ylUfNzE, gkisf1CYj3A, TJCFX9-TW5Q, 6UHnCdw_hvM, IX0Sivi6meg (sidebar card), 1cbDSZlchS0, k2mjZC0Yn8Q; no captions at all: EdwVYhUMN78, w7128woejms, 27SX-xLPwGU, 75n7ZYzkLHw, CmI4zwSAajw, oNuFCh7jshQ; i-jMhZZf9a4 is a multi-hour marathon livestream (metadata only).
- Page-only records (no video): mir.works summit tutorials (6, Vimeo), polyhop (5, Vimeo), JenV samples, 61123, 62519, 62580, 62746. Their records come from the blurb/timestamps; steps are coarse.
- Caveat: 62532 (Blender UV unwrap) is a French Vimeo video; the YouTube link in its page source is another post's card (Dean Cheesman point-cloud sprinkles, 2025, transcript kept in the transcripts folder but not a record here). 62707 and 62717 and 62229 have similar sidebar-card video links; the records use only each post's own video.
- Files downloaded (free, no login, <= 50 MB, never opened): 18 .toe/.tox/.zip attachments + shallow git clones for 62083-62086, 62655 (TD-Tutorials), 62695/62713 (Twitter), 62745 (Raymarching-in-TD), 61021/61022/61023 (mir-lab, template tox). Patreon-only/paid: 62656/62657 (elekktronaut), 62576/62600 (exsstas example file), 62519 (EnviralDesign), 75505 (SD TOP, paid operator), 75535 (focus/grain).

## Top 15 as rebuild recipes (ops in order, key params)
1. **75525 Audio Reactive Particles using TouchDesigner POPs** (elburz, 2026-10-19, POP)
   Ops: pointgeneratorPOP, randomPOP, attributePOP, particlePOP, inPOP, mathcombinePOP, outPOP, nullPOP, trailPOP, rayPOP, boxPOP, geometryCOMP, cameraCOMP, lightCOMP, lineMAT, renderTOP
   Params: birth rate=50..1000; gravity=age*0.1; trail=match by PartID; max particles=raise to avoid flicker; render=32-bit float
   - Render setup: pointgeneratorPOP (tiny sphere source) -> geometryCOMP + camera + light + renderTOP -> null; black via transform; Line MAT with draw points to see points
   - randomPOP (size 3, no add to P, output attribute N, range -1..1) -> sets a direction per point; random magnitude gives speed variety
   - attributePOP creates Color (orange-ish) and randomPOP creates Line width; in particlePOP Input Attributes tick Color + LineWidth so they survive the feedback
   Trick: Particle POP creates PartID, age, velocity attributes automatically; add custom attributes to its Input Attributes list
2. **75531 Rolling Tiles using POPs, CHOPs, and DATs** (vtln, 2026-10-20, POP)
   Ops: containerCOMP, parameterCHOP, mathCHOP, nullCHOP, gridPOP, mergeCHOP, fieldPOP, patternCHOP, tableDAT, beatCHOP, noiseCHOP, chopexecuteDAT, constantCHOP, selectDAT, insertDAT, mergeDAT
   Params: speed=0.005; beat period=small; circle divisions=20
   - Parameter CHOP reads parent width/height -> aspect ratio A; gridPOP columns/rows/size; cell size = sizeX/(cols-1), sizeY/(rows-1) with math pre-add -1
   - fieldPOP box mode (weight) = a selectable band; position/size will be written by export
   - patternCHOP ramp (length=cols, range -sizeX/2..sizeX/2) + CHOP to DAT gives column/row coordinates (two copies for X and Y)
   Trick: Export table DAT with path/parameter/enable/value columns is a compact way to drive many params from one CHOP
3. **62551 Beat Detection** (elekktronaut, 2020-02-13, audio)
   Ops: baseCOMP, inCHOP, outCHOP, audiofileinCHOP, mathCHOP, audiospectrumCHOP, analyzeCHOP, trailCHOP, limitCHOP, triggerCHOP, selectCHOP, trimCHOP, nullCHOP
   Params: multiply=1000; limit clamp min=87; trigger threshold=0.5; trigger min sustain=0.1; trim upper=0.6
   - Base COMP with In/Out CHOPs; audio source stays outside the base; name it 'kick_detection'
   - mathCHOP combine channels = average (stereo -> mono)
   - audiospectrumCHOP, high-frequency boost 1
   Trick: Kick is easiest: biggest energy; tune threshold per song
4. **62696 VJSet + OSC - PROGRAMACIXN PARA HUMANXS - DIA 2** (videoso, 2020-03-26, camera/interactive)
   Ops: oscinCHOP, inCHOP, outCHOP, blurTOP, displaceTOP, edgeTOP, levelTOP, moviefileinTOP, compositeTOP, nullTOP, inTOP, windowCOMP, containerCOMP, selectCHOP, mathCHOP
   Params: osc ports used=7000 (pad app), 7400 (sensor app), TD default 10000; composite operation=Add; level target par=Post Opacity (Post page); window monitor=0; fps target=60
   - OSC concept: protocol for live music/show devices over a network; the PC is the 'host' (receiver). Find host IP (Windows: cmd > ipconfig > IPv4 address; Mac: System Settings ...
   - Add OSC In CHOP (Tab 'osc'; pick 'OSC In CHOP', not the DAT). Network Port must equal the app's port: he changes 8000 -> 7000 for the 4-pad app (TD default is 10000) and 7400...
   - Sensor app (Android): sends accelerometer (3 axes + gravity/linear acceleration), gyro, light, proximity, GPS, WiFi strength as /... addresses at once; light is a float, prox...
   Trick: IP and port must match exactly; OSC In shows channels only after each address has sent once
5. **62671 Slit Scan - Touchdesigner tutorial** (tolch, 2020-03-20, TOP)
   Ops: moviefileinTOP, infoCHOP, rectangleTOP, compositeTOP, feedbackTOP, texture3dTOP, rampTOP, timemachineTOP, switchTOP, lfoCHOP, containerCOMP, videodeviceinTOP
   Params: slit rect size=0.01 x 1; video/ramp res=1280x720; texture3d cache=32-200 frames; black offset=-cache size; pixel format=32-bit float
   - Method 1: Movie File In TOP (1280x720). Info CHOP on it gives index/length/frames; pick the field you need to scrub (the frame position)
   - Rectangle TOP, resolution 1280x720, size X 0.01, size Y 1 (thin slit)
   - Composite TOP (Multiply) of video and slit; Feedback TOP -> Composite TOP 2 (operation Over: the feedback below, new slice above); composite 1 into composite 2; drag composit...
   Trick: Greyscale map must have the same resolution as the video
6. **62749 Noise Generator - Touchdesigner tutorial 1** (47vizn, 2020-04-07, TOP)
   Ops: baseCOMP, rectangleTOP, noiseTOP, displaceTOP, lfoCHOP, mathCHOP, compositeTOP, levelTOP, nullTOP, lookupTOP, rampTOP, rgbkeyTOP, hsvadjustTOP, blurTOP, constantCHOP, speedCHOP
   Params: grain amplitude=80; grain exponent== amount; flare noise period=12; flare level gamma=1.2; flare level contrast=2.19
   - Fade: rectangleTOP size 0 -> level (gamma lifts blacks); fill alpha later = fade amount 0..0.5
   - Grain: noiseTOP 1280x1280 8-bit (do NOT raise bit depth), amplitude 80, offset 1, exponent = Amount, scale animated absTime.seconds*0.05; displaceTOP with a rectangle (size 0...
   - Glitch/TV: copy grain, offset ~0.01-0.1 range referenced to param
   Trick: 8-bit pixel format for grain, higher bit depth produces other glitch looks
7. **62576 Working with vertex shaders (GLSL MAT) - Part 1/2** (exsstas, 2020-02-19, GLSL)
   Ops: tubeSOP, facetSOP, geometryCOMP, cameraCOMP, lightCOMP, renderTOP, phongMAT, glslMAT, noiseTOP, torusSOP, sortSOP, mathCHOP, nullCHOP
   Params: tube rows/cols=500; tube height=2; noise period=low for large blobs; primitive type menu index=quads=4, triangles=3 via expression; TOP pixel format for position=32-bit float, nearest pixel
   - Setup: Tube SOP (primitive type Polygon, narrow, height 2, ~500 rows/cols so it deforms smoothly) -> Facet SOP (will be toggled Unique Points + Compute Normals later) -> Geom...
   - Create a Phong MAT first (diffuse colour, optionally colour map), then in its panel press 'Output Shader' -> a GLSL MAT is created with vertex + pixel + info DATs already hol...
   - Vertex pipeline: geometry sends P and N into the vertex shader; vertex shader outputs world position, normal, colour, camera index to the pixel shader. TD provides P (vec3 ve...
   Trick: Always create the GLSL MAT via Output Shader from a Phong/PBR MAT: you get all TD uniforms/varyings for free (MAT from scratch is empty).
8. **62745 Raymarching in TouchDesigner tutorial series** (exsstas, 2020-04-06, GLSL)
   Ops: glslTOP, textDAT, tableDAT, nullCHOP, mathCHOP, noiseCHOP, audiodeviceinCHOP, audiospectrumCHOP, analyzeCHOP, filterCHOP, mergeCHOP, noiseTOP, mathTOP, levelTOP, nullTOP, cubemapTOP
   Params: MAX_DIST=20 default, 100-200 for far scenes; MIN_DIST=~0.001; step multiplier for warped SDF=0.55-0.6 (1.0 = exact); reflections=4-7; color buffers=up to 8 (author uses 2-6)
   - PART 1 -- scene description. Template GLSL TOP (uniforms on the Vectors page, shader code in the GLSL TOP's pixel-shader text DAT). Download repo; open tutorial part 1 toe. O...
   - Core contract: 'float sceneSDF(vec3 p)' returns signed distance to nearest surface: negative inside, 0 on surface, positive outside. Marching: start at camera, step along ray...
   - Sphere: 'return sphereSDF(p - center, radius)'. IMPORTANT: you do not move the object, you move the space: 'vec3 q = p - uOffset;' (uOffset=vec3 uniform); do the position sub...
   Trick: Move the space, not the object: subtract the position from p before calling a primitive.
9. **62036 Point Clouds in TouchDesigner** (snaut, 2019-11-08, SOP)
   Ops: boxSOP, copySOP, noiseTOP, nullCHOP, nullTOP, mergeCHOP, geometryCOMP, reorderTOP, constantMAT, phongMAT, baseCOMP
   Params: divisions=4x4x4 (up to 23^3 with instancing); noise translate z=absTime.seconds*0.2
   - Template boxSOP with divisions 4x4x4; copySOP: input1 = small box (size 0.1), input2 = template; turn off rotate to normal; use template point attributes
   - noiseTOP (monochrome off, simplex 3D): feed point positions as noise coordinate map: sopToCHOP -> nullCHOP -> chopToTOP (RGB) into noiseTOP input 2 (and input 1 to get 64x1 r...
   - topToCHOP (channels r g b) -> chopToSOP inserted between box and copySOP with channel scope r g b and attribute scope CD0 CD1 CD2 (point colour), then enable use template poi...
   Trick: Right-click a wire to insert an op between
10. **62255 Kinetic Typography in TouchDesigner - Part 1 The Fundament** (Artechs, 2019-12-28, typography)
   Ops: baseCOMP, patternCHOP, mergeCHOP, limitCHOP, railsSOP, rectangleSOP, nullSOP, tableDAT, evaluateDAT, insertDAT, mergeDAT, selectDAT, textDAT, lookupDAT, sortDAT, textTOP
   Params: sentence length example=40; cycles X=3; rail rotate=-90; speed=-1
   - Pattern CHOPs sized by sentence length (op().numRows expression): TX = sine 3 cycles, DY = sine 1 cycle, DZ = cosine 3 cycles; merge
   - Rails SOP between the path curve and an offset copy ('little brother') using a Rectangle SOP as profile; rotate -90; use primitive normals (point normals did not work)
   - Extract per-primitive data: Table DAT rows = num prims, Evaluate DAT with expression like op('null').prim(me.inputCell.row).x/y/z and normal; Insert DAT names columns
   Trick: Use primitive normals via Rails; point normals failed
11. **75551 Using the New Timecode Features in TouchDesigner** (elburz, 2026-10-23, Python)
   Ops: moviefileinTOP, audiofileinCHOP, audiodeviceoutCHOP, edgeTOP, lensdistortTOP, lookupTOP, rampTOP, switchTOP, nullTOP, blurTOP, levelTOP, constantTOP, overTOP, timerCHOP, selectCHOP, mathCHOP
   Params: timer length=8; video cues=0,20,36,42 s; song cues=0 reset, 140 blur on, 160 fade
   - Project in its own folder with an assets folder; movie file in + two audio file in CHOPs (chime with repeat off, cued by pulse); audio device outs
   - Effects: edge, lens distort and lookup (ramp red -> blue) all into a switchTOP (original video at index 0) -> null
   - opexecuteDAT: monitor the movie; enable Post Cook; in onPostCook: t = changeOp.timeCode; frame=t.frame; sec=t.second; run only when frame==0 (else it fires fps times per seco...
   Trick: Fire events only on frame==0 of the second to avoid 30 executions/second
12. **62656 Pixel Sorting** (elekktronaut, 2020-03-18, TOP)
   Ops: moviefileinTOP, switchTOP, fitTOP, feedbackTOP, compositeTOP, displaceTOP, levelTOP, subtractTOP, transformTOP, keyboardinCHOP, nullTOP
   Params: displace weight=0.01; level brightness=0.1; fit res=1920x1920
   - moviefileinTOP x4 -> switchTOP -> fitTOP (fit outside, 1920x1920)
   - feedbackTOP with target BG transform
   - In the loop: compositeTOP (operation Difference) then displaceTOP (source midpoint 0, displace weight ~0.01)
   Trick: Difference in a feedback loop gives the smearing
13. **62665 DMX-Controller** (alphamoonbase, 2020-03-20, workflow)
   Ops: baseCOMP, parameterCHOP, mathCHOP, renameCHOP, nullCHOP, constantCHOP, selectCHOP, replaceCHOP, dmxoutCHOP, dmxinCHOP, opfindDAT, parameterCOMP, containerCOMP, tableDAT
   Params: universe size=512; footprint=3; math range=0..255
   - Fixture base: custom pars page Control (RGB 'color', float 'master'), page Settings (int 'address' 1..512, read-only 'footprint'=3)
   - parameterCHOP color* -> mathCHOP range to 0..255 + round; second parameterCHOP master -> math; combine multiply; rename to 'ch{}' via expression 'ch{}'.format(parent().par.ad...
   - Universe: constantCHOP 512 channels names ch{1..512} (expression), value 0; selectCHOP with relative path to each fixture's DMXout; replaceCHOP overwrites universe slots
   Trick: Any fixture type only has to expose a 'DMXout' CHOP
14. **62217 TOPs: FX VHS con Displace y Noise - TouchDesigner para principiantes.** (gnomalab, 2019-12-10, TOP)
   Ops: moviefileinTOP, outTOP, displaceTOP, noiseTOP, compositeTOP, rampTOP, levelTOP, nullTOP
   Params: noise resolution=1280x720; noise pixel format=32-bit float; displace weight=~0.1 (low); composite op=Maximum; x weights=0.05 / -0.05
   - Inside a Base COMP: Movie File In TOP (default banana image is fine) -> Out TOP so you have a viewer
   - Insert a Displace TOP: input 0 = the image, input 1 = displacement map. Add a Noise TOP into input 1
   - Displace TOP: set displacement weights (X/Y) to a very low value such as 0 on one axis and ~0.1 on the other so you get gentle distortion
   Trick: Match the noise resolution to the video resolution, otherwise displacement looks soft
15. **61081 Touchdesigner + Resolume: comunicación bidireccional** (tolch, 2019-10-16, output)
   Ops: syphonspoutoutTOP, syphonspoutinTOP, oscoutCHOP, oscinCHOP, oscoutDAT, oscinDAT
   Params: dummy plugin variants=4, 8, 12, 16 parameters; video=Spout (Win) / Syphon (Mac); control=OSC
   - From the description: download the dummy-parameter FFGL plugin builds (Leskos/FFGLDummyParams, and the release page subpixels.com/resolume/ffgl/release/); source for FFGL its...
   - The .dll files with 4, 8, 12 and 16 dummy parameters go into Resolume's plugins/vfx folder; restart Resolume and they show up in the Effects section
   - Add a dummy-parameter effect to a layer/clip: its generic sliders become the knobs you map to TouchDesigner; this is what makes arbitrary external control possible
   Trick: Use the dummy parameter FFGL plugins to get extra sliders in Resolume for OSC bridging

## Recurring techniques and ops
- Most used ops (count of posts): mathCHOP 33, geometryCOMP 32, renderTOP 27, cameraCOMP 27, nullTOP 21, levelTOP 21, nullCHOP 19, compositeTOP 19, selectCHOP 19, lightCOMP 18, mergeCHOP 15, noiseCHOP 15, phongMAT 15, moviefileinTOP 15, noiseTOP 15, constantCHOP 15, rampTOP 14, containerCOMP 13, baseCOMP 11, transformTOP 11, constantMAT 11, blurTOP 11
- Audio-reactive chain: audio in -> math (average/RMS) -> analyze/trail -> limit/trigger -> parameter reference (62551, 61100-61102, 75525, 62730, 62724).
- Instancing from CHOP/DAT/TOP data: noise CHOP/TOP -> math -> Geometry COMP instance (62036, 62084, 62657, 62255); in 2025 per-attribute OP sources and POPs replace most of the SOP/Copy tricks.
- Feedback + displace/difference for glitch/trail looks (62656, 62694, 62612, 62217); Texture 3D / Time Machine for slit-scan (62671).
- Custom parameters + Base COMP as a reusable effect (62749, 62665, 62135); Global OP Shortcuts for UI (62669).
- Python: CHOP/OP Execute with frame guards (75551), Evaluate/Table DAT scripts (62255), extensions (mir.works).
- POPs (new in 2025): Particle POP feedback loop with attributes, Trail POP by PartID, Field/Feedback/Limit/Quantize POPs for grids (75525, 75531, 75535).
- Top authors: tolch (15), videoso (7), mir.works (6), elekktronaut (6), gnomalab (6), polyhop (5), Artechs (4), snaut (3), exsstas (3)

## Changed in TD 2025 / obsolete workflows (flagged per record in `changed_in_2025`)
- Particle SOP / Spring SOP / Copy SOP workflows (62609, 62611, 62706, 62707, 62733, 62036): rebuild with Particle POP, Copy POP, instancing with separate OP per attribute.
- GLSL: 2018-2020 GLSL TOP/MAT templates (61132, 62576, 62600, 62745): Output Shader button, TDOutputSwizzle, sTD2DInputs are still valid; check uniform/array page UI and Vulkan/MoltenVK differences on 31550.
- Texture instancing (62255 part 1 vs 62711 workaround): the 'instancing texture not supported' error was a 2019 Mac/Kepler limit; instance-per-attribute OPs now cover it.
- Twitter API tutorials (62695, 62713): v1.1 free access is gone; keep the Web Client DAT + OAuth + saveByteArray patterns only.
- Resolume 6 era FFGL dummy-parameter plugins (61081): Resolume 7.23.2 has native OSC/REST; the .dll is Windows-only; re-verify OSC addresses with `learn`.
- Python/ML 'LEGO' stack (62675): TF 1.x/CUDA 10, Spout, hidden pygame window; 2025 builds ship Python 3.11 and a Python environment manager.
- Timecode class (75551, 2026): `op.timeCode` members documented for the new TD build; verify on 31550 before use.

## Newer-build / Windows-only / missing-op flags
- NVIDIA Flow (62717, 62662): Windows + NVIDIA only; not in our build.
- Spout (62724, 62675, 61081): Windows; use Syphon Spout In/Out TOPs on Mac. TDAbleton (61100-61102), ASIO4ALL/VB-Cable (62724), Kinect v1/v2 (62712), Leap Motion (61032) are Windows/hardware specific.
- SD TOP (75505): third-party paid C++ operator; no spoken instruction in the video.
- Device/IO ops (keyboardin, mousein, midi, osc, dmx, audiodevice, video device, kinect) are real TD ops that our `INDEX_2025.31550.json` simply does not list; only genuinely absent ops are in `ops_not_in_31550`.
