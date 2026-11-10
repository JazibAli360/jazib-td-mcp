# Tutorials slice 02 (derivative.ca tutorial listing pages 6-11), 26 Oct 2026

Slice agent NN=02. Listing `https://derivative.ca/community?sort_by=created&type[]=23&page=6..11` (pages 6-11 = 120 listing slots, newest-first as of 26 Oct 2026). Pagination shifted while crawling, so 25 posts repeated across pages: **95 unique tutorial posts** read (Oct 2026 back to 1 Jun 2025). Data: `research_src/tutorials/slice_02.jsonl` (one line per post, schema from BRIEF), transcripts: `research_src/tutorials/transcripts/<videoid>.txt` (+ raw `.en-orig.vtt`). All page/video text treated as data. Author field = the derivative.ca account (`elburz` = The Interactive & Immersive HQ account, which hosts several presenters: Jack DiLaura, Christian Kastner, Marco/Reflekkt, Crystal, Lake Heckaman, Scott Mann, Joel).

## Counts per category (my classification of what each tutorial teaches)
| category | n | | category | n |
|---|---|---|---|---|
| POP | 21 | | 3D/render | 12 |
| ML/AI | 10 | | workflow | 10 |
| TOP | 6 | | camera/interactive | 6 |
| GLSL | 5 | | COMP/UI | 5 |
| audio | 5 | | mapping | 4 |
| output | 4 | | Python | 2 |
| typography | 2 | | CHOP | 2 |
| SOP | 1 | |  |  |

Relevance (0-3 general TD mastery): 3 = 47, 2 = 30, 1 = 17, 0 = 1. POP family is the biggest topic (21 posts, since POPs went official in 2025.31500).

## Transcripts
- Fetched (YouTube auto captions, English original track `en-orig`; Spanish `es-orig` for the one Spanish video): **84 of 95 posts** (93 distinct primary videos plus one playlist-only post); video metadata (channel, duration, views, likes, chapters) is in each jsonl record.
- Without a transcript (11): ten videos have **no captions published at all** (all from the audiodevout channel: 73912, 73830, 73270, 73269, 73009, 72954, 72896, 72808, 72722, 72685; recorded from blurb/description only) plus 72434 (playlist-only post, no embedded video). Details are in each record's `teaches`.
- No YouTube rate-limit block was hit apart from one HTTP 429 on a subtitle request (other agents share the IP); the 5-minute pause and a second pass fixed it. The first calls requested `en` and `en-orig`; after the 429 the script requested `en-orig` only (fallback `en`). Never downloaded video or audio.
- Caption quality: auto-captions garble op names (e.g. 'fong mat' = Phong MAT, 'soop' = SOP, 'chop' ok); records use the proper op class names and were cross-checked with the 31550 op index.
- Files: only one derivative.ca attachment existed (72372 `Project File.toe`, 4,690 bytes, saved to `research_src/tutorials/files/72372/build.toe`, never opened). Other project files are Patreon, email-gated (IIHQ), Discord or Google Drive links (recorded in `files`, not fetched).

## Top 15 as rebuild recipes (ops in order, key params; full steps in the jsonl)
### 1. Audio Reactive Particles using TouchDesigner POPs (75525) - The Interactive & Immersive HQ, 2026-10-19, POP
Ops: pointgeneratorPOP > randomPOP > attributePOP > particlePOP > inPOP > outPOP > rayPOP > noiseCHOP > audiofileinCHOP > audiospectrumCHOP > analyzeCHOP > mathCHOP > renderTOP > blurTOP > levelTOP
Params: birth rate=50-1000 driven by level 0..0.5; render=32-bit float
Gotchas: Particle POP is its own feedback loop - needs the loop target set | Turn on built-in attributes in the Particle POP list or they are lost
### 2. Rolling Tiles using POPs, CHOPs, and DATs (75531) - VTLN, 2026-10-20, POP
Ops: gridPOP > parameterCHOP > mathCHOP > nullCHOP > fieldPOP > patternCHOP > constantCHOP > noiseCHOP > chopexecuteDAT > selectCHOP > tableDAT > insertDAT > mergeDAT > transposeCHOP > keyboardinCHOP > expressionCHOP
Params: noise Chop=offset 0.5, very small period; speed=0.005; circle divisions=20; delay=1 ms (not 1 frame)
Gotchas: CHOP export via a DAT table (path/parameter/enable/value) lets Python flip which parameter is driven | Rename pattern CHOPs/channels so the table references stay readable
### 3. Surface Trails on any Geometry using TouchDesigner POPs (73881) - The Interactive & Immersive HQ, 2026-02-02, POP
Ops: pointgeneratorPOP > noisePOP > rayPOP > normalPOP > nullPOP > trailPOP > lineresamplePOP > linemetricsPOP > mathmixPOP > copyPOP > circlePOP > skinPOP > lookuptexturePOP > geometryCOMP > cameraCOMP > lightCOMP
Params: points=1000; resample=50 divisions per line strip; circle radius=0.02
Gotchas: If rays leave the model, the point generator is partly outside the mesh | Point count in the generator controls Ray POP output count
### 4. Speed Controls Tutorial (73904) - tekt, 2026-02-05, CHOP
Ops: baseCOMP > boxSOP > cameraCOMP > lightCOMP > renderTOP > parameterCHOP > selectCHOP > mathCHOP > speedCHOP > lfoCHOP > nullCHOP
Params: speed multiply=45; spin range=-1..1; Speed CHOP=reset + limit/wrap for long runs
Gotchas: Never drive speed from absTime directly: you cannot slow or reverse it without a jump | Speed CHOP integrates so setting speed to 0 freezes at the current value
### 5. Build Your Own VJ Crossfader (73803) - tekt, 2026-01-21, COMP/UI
Ops: noiseTOP > fitTOP > resolutionTOP > nullTOP > baseCOMP > inTOP > outTOP > crossTOP > compositeTOP > switchTOP > mathCHOP > filterCHOP > containerCOMP > buttonCOMP > sliderCOMP > textCOMP
Params: crossfade=-1..1; fade time=default 1, max 10; settings button=30x30
Gotchas: Develop reusable components with parameters and a separate UI layer | Unit-label time parameters (seconds)
### 6. Sharing audio reactivity across scenes (73652) - tekt, 2026-01-03, audio
Ops: audiofileinCHOP > audiodeviceinCHOP > switchCHOP > mathCHOP > audiospectrumCHOP > nullCHOP > constantCHOP > replaceCHOP > filterCHOP > limitCHOP > noiseCHOP > circleTOP
Params: filter width=0.2; radius range=0.3..0.6
Gotchas: Make scenes degrade gracefully (placeholder chops with same channel names) so they never error without the audio source | Shortcut name need not equal operator name
### 7. Simple Particle Systems with TouchDesigner TOPs (73598) - The Interactive & Immersive HQ, 2025-12-22, POP
Ops: infoCHOP > thresholdTOP > rampTOP > reorderTOP > selectTOP > particlesGpuCOMP > compositeTOP > resolutionTOP > feedbackTOP
Params: particles=1M; initial velocity=0.4; turbulence=0.4; texture=512x512 32-bit float
Gotchas: Use 32-bit float in the feedback to avoid ghosting that never fades | Convert aspect via point transform scale = res X / res Y
### 8. TouchDesigner Glitch Feedback in Post Processing (73573) - The Interactive & Immersive HQ, 2025-12-17, TOP
Ops: constantCHOP > boxSOP > copySOP > geometryCOMP > renderTOP > feedbackTOP > noiseTOP > thresholdTOP > multiplyTOP > crossTOP > compositeTOP > addTOP > blurTOP > inTOP
Params: copies=50-80; scale=0.99; angle=0.5 deg; threshold soften=4 px; format=16-bit float
Gotchas: Depth test 'always' for wireframe feedback renders | Feed only a masked portion of the new frame into a static feedback node for 'buffering' glitches
### 9. TouchDesigner Glitch Effect with GLSL (73842) - The Interactive & Immersive HQ, 2026-01-26, GLSL
Ops: constantCHOP > speedCHOP > nullCHOP > glslTOP > feedbackTOP
Params: slices=10; uv offset=1/2; colour offset=1/6; extend=Repeat
Gotchas: Time stops = glitch stops: drive uTime from a Speed CHOP for control | Use Extend Mode Repeat to remove holes after UV offsets
### 10. GLSL Slit Scan Effect in TouchDesigner (74007) - The Interactive & Immersive HQ, 2026-02-22, GLSL
Ops: moviefileinTOP > fitTOP > infoCHOP > feedbackTOP > glslTOP > nullTOP > outTOP
Params: uSlit=0.2 .. 0.8; shift=1 texel * scan speed per frame
Gotchas: Reset the feedback after changing the shader | Custom parameters on the GLSL TOP replace hard-coded numbers
### 11. Live Performance Rig Tutorial (72078) - tekt, 2025-06-01, output
Ops: outTOP > switchTOP > selectTOP > levelTOP > crossTOP > constantTOP > nullTOP > parameterCOMP > windowCOMP > baseCOMP > midiinCHOP
Params: MIDI range=0..1
Gotchas: Dragging a parameter onto Function Store's button creates a linked parameter on the parent | Keep all scenes at one resolution
### 12. LED Pixel Mapping in TouchDesigner (73800) - The Interactive & Immersive HQ, 2026-01-21, mapping
Ops: rampTOP > cropTOP > toptoCHOP > mergeCHOP > mathCHOP > shuffleCHOP > selectCHOP > stretchCHOP > reorderCHOP > dmxoutCHOP
Params: universe size=510 samples; brightness cap=0..150; matrix=2 x 8x32 -> 16x32
Gotchas: DMX Out needs constant cooking | Keep 510 (3 x 170) not 512 per universe so RGB triples are never split
### 13. 3D Flocking with POPs (73049) - Dean Cheesman, 2025-10-16, POP
Ops: pointgeneratorPOP > randomPOP > feedbackPOP > neighborPOP > mathPOP > mathcombinePOP > noisePOP > copyPOP > geometryCOMP > cameraCOMP > renderTOP > rampTOP > feedbackTOP > keyboardinCHOP > constantCHOP
Params: points=400 build -> 4000 final at 60 fps; attract/align/repel=0.5 / 0.3 / 0.25; render=1080x1920
Gotchas: Too many points into a POP op can blow up on a Mac: build small, scale up | Hit the reset (1) key after parameter changes in feedback sims
### 14. Resilient TouchDesigner Installations (72892) - tekt, 2025-09-26, workflow
Ops: oscinCHOP > constantCHOP > replaceCHOP > keyboardinCHOP > mathCHOP > nullCHOP > shuffleCHOP > selectCHOP > tableDAT > sphereSOP > geometryCOMP > cameraCOMP > renderTOP > constantTOP > midioutCHOP > windowCOMP
Params: scale range=0.2..1.2; midi note offset=n<note>
Gotchas: Make the data model a table, not N copies of ops | Fake every external input with the keyboard so you can test off-site
### 15. Make Complex Video Loops with Particles (72646) - Dean Cheesman, 2025-08-20, TOP
Ops: lfoCHOP > patternCHOP > noiseTOP > slopeTOP > displaceTOP > remapTOP > mathTOP > geometryCOMP > cameraCOMP > renderTOP > timerCHOP > moviefileoutTOP > moviefileinTOP
Params: loop=5 s; res=1080x1920; sample tex=1280x1280 32-bit float; scale=0.001 size / 0.004 height
Gotchas: Circle path (sin+cos) through 4D noise gives a mathematically perfect loop | Test the seam by recording exactly one loop length

## Recurring techniques and ops
- Most-used ops across the slice: geometryCOMP (39 posts), renderTOP (33), cameraCOMP (28), mathCHOP (23), feedbackTOP (22), noiseTOP (19), nullTOP (19), nullCHOP (16), rampTOP (15), switchTOP/lightCOMP (14).
- **POPs** (21 posts): the standard chain is pointgeneratorPOP/gridPOP > randomPOP/attributePOP > particlePOP (own feedback) or feedbackPOP (needs memory limit) > noisePOP/mathmixPOP/fieldPOP > lookuptexturePOP / trailPOP > geometryCOMP (drag output + Tab) > renderTOP > bloomTOP. toptoPOP/poptoTOP bridge to textures; attributes (point/primitive level, P copy, normalised age) are the core concept. rayPOP + trailPOP + skinPOP for surface trails; neighborPOP/proximityPOP for flocking and plexus.
- **Feedback** everywhere: feedbackTOP with lowered input opacity (0.3), 16/32-bit float formats, Keyboard In (key 1) reset, Cross TOP + noise/threshold mask for glitch buffering.
- **GLSL TOP snippets** (5 posts): slit scan, VHS glitch, Bayer dither, Sobel, audio-reactive ShaderToy port; always expose uniforms as custom parameters on the GLSL TOP.
- **Audio-reactive**: audiofileinCHOP > audiospectrumCHOP > resample/analyze/math range > chop reference; TDAbleton for Ableton; keep fps matched to the downstream (30 for StreamDiffusion).
- **System design (tekt)**: scenes as COMPs with one Out TOP + resolution parameter; OP shortcuts for shared data; Engine COMP for isolated loading; Speed CHOP not absTime; Parameter Execute / Execute DAT start-up loaders; perform mode (F1) and Window COMP for output.
- **LED / mapping**: WLED+ESP32 8x32 matrices via DDP/Art-Net/sACN, 510-sample universes, Shuffle/Stretch/Reorder CHOPs to undo serpentine order; PixLite + Art-Net with 500-pixel outputs.
- **AI**: StreamDiffusionTD (Daydream remote service), ComfyTD, DepthAnything and MediaPipe (both Mac+PC), Video Depth Anything for depth-to-point-cloud, Teachable Machine; all third-party tox files.

## Top authors (posts in this slice)
elburz / IIHQ 37, tekt 16, audiodevout 10 (no captions), dcheesman 6, pao.olea 4, Unveil_studio 4, cmuir 3, elekktronaut 2, blankensmithing 2, then single posts. Most useful per post: tekt (architecture and UI), IIHQ (POPs, GLSL), Dean Cheesman (Mac, POPs), elekktronaut (POP experiments), Function Store (CHOP anatomy).

## Newer-build and platform flags
- **POPs need 2025.31500 or newer** (official). Several tutorials were recorded on experimental builds: 2025.30280 (Cheesman, Mac), 2025.31310 (teapot), pre-31500 alpha (72444 needed an emailed access). Parameter names may differ slightly from 31550; always check with `td_get_pars`. Ops mentioned by the speakers that are absent from the 31550 class list: `transposeCHOP`, `slitscanTOP`, `fractalTOP`, `rgbadelayTOP` (probably palette or older/custom components), `sdTOP`/`comfytd`/`streamdiffusionTD`/`depthanything`/`mediapipe`/`teachablemachine`/RayTK ops/`particlesGpuCOMP`/`autouiCOMP`/`tdabletonCOMP` (third-party or palette tox, not built-in).
- **Rendering helpers new in the POP era**: `rendersimpleTOP` (POP straight to render, no Geo/Cam/Light), `linebreakPOP`, `poptoTOP`, `toptoPOP`, `rerangePOP`: all present in 31550.
- **Windows / NVIDIA only**: Body Track CHOP (72716), NVIDIA Background Removal TOP (72113), NVIDIA Upscaler TOP and StreamDiffusion toolkit (72128; Python 3.11.9 + CUDA 11.8/12.1), NVIDIA Flex (73269, 72492), Spout in the Unreal pipeline (72666; Syphon on Mac). RayTK author used Windows+NVIDIA (73793), plugin is GLSL so likely fine on Mac.
- **Mac-friendly confirmed in videos**: Dean Cheesman builds POPs on a Mac (flocking 73049, sprinkles 72435; warns that too many points into a new op can blow up on Mac), MediaPipe plugin Mac+PC (72830, 72299 with Mac MIDI IAC routing), DepthAnything Mac+PC (73018), TDAbleton.
- Older-build items: Perform Mode video used 2023.12370 (Window COMP parameter pages differ); ENNEAGRAMM grids 2023.11340; RayTK 0.45 needed the production build, 0.46+ needs 2025 experimental.

## Tutorials of note not in the top 15
73406 ParticlesGPU forces (Scott Mann), 73967 point typography (Render Simple POP), 73188 3D render tips (SSAO, IBL, tone map), 72359/72436/72536 scene loading trilogy, 72725/72711 UI layouts and widgets, 72855 TDAbleton concert visuals, 72830/72299 MediaPipe, 73018 DepthAnything, 72708 Bayer dither GLSL, 72286 Sobel GLSL, 73090 CHOP anatomy (cook-time and frame-budget facts), 73262/73194/73064 workflow and version-pinning essays.
