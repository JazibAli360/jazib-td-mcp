# Tutorials slice 06 - derivative.ca listing pages 30-35 (26 Oct 2026)

Listing `community?sort_by=created&type[]=23&page=30..35`: 6 pages x 20 rows = 120 rows, **95 unique tutorial posts** (the same post can appear twice across pages; the two 'python type hints' posts and the two Spanish/English Kinect-Ableton posts are separate posts). Posts date from 2022-01 to 2022-12, plus 5 posts from Oct 2026 (POP era). Data: `research_src/tutorials/slice_06.jsonl`. Transcripts: `research_src/tutorials/transcripts/<videoid>.txt` (shared folder). Build behind each live claim = the build named in the video; all videos are 2021-2022 builds unless noted; the 2026 ones use POPs (2025.x).

## Counts per category

3D/render 15 | TOP 12 | COMP/UI 9 | camera/interactive 9 | Python 9 | workflow 9 | SOP 6 | audio 6 | ML/AI 5 | output 4 | CHOP 4 | POP 3 | GLSL 3 | other 1

## Transcripts

- Posts: 95. With a video: 91 posts (90 distinct videos). No video (text tutorials): 4 (66888, 66947, 66433, 66288).
- Transcripts fetched: 79 of 90 distinct videos (YouTube auto/manual English captions via yt-dlp, no download of media).
- No transcript: 11: 5EyN_3vIqys (Generative Camera Paths in TouchDesigner); Oe0D_cVQmjE (2DVector Fields 2D for .. particle syste); TJlU3AOOwzU (Lines); UrZgDGxFZsQ (Elgato Stream Deck + TouchDesigner - Tut); jq-7ro5HfT0 (Shader Park Plugin for TouchDesigner + A); keVyiCBHWhI (Nvidia Flex Basics in TouchDesigner); nbaNuPBqv0E (Instrumentos Controlados por Movimiento ); s4ytd8PThJM (Reaction-Diffusion Feedback Effects in T); ssJUxwtR44o (ATTRAKTORS DESIGNER v0.7 - Tutorial #1 -); va6cxORsFMw (Talking Ball Starboy in TouchDesigner (터); yGjyT94jdTA (Julio Le Parc-style Generative Op Art in). All hit HTTP 429 on the subtitle endpoint (metadata/chapters still fetched; several agents share the IP); retried after 5-minute pauses in 2 passes, then stopped per the manners. These 11 records are analysed from description + chapters + post text only (`analysis_source` says so, ops are conservative guesses) - re-run `yt-dlp --write-auto-subs` for them later. Korean (va6cxORsFMw) and Spanish (nbaNuPBqv0E, same video as vHtUXvb6XMM) were not fetched in their original language.
- Wrong video on the site: post 66017 (QR Code Photobooth) links the Bridget Riley video (gRIJ8tX9PiE); the real video `t8tIc5b58qM` was found by title search. Websocket part 2 post links part 1's video; real part 2 = `m5k8d4bmoUU` (playlist order).

## Top 15 as rebuild recipes

1. **The Secret of Feedback Loops in TouchDesigner - Tutorial** (elburz, 2022-05-05) `66168` video `JkKHKsY31no` 1362s
   - Ops: constantTOP > circleTOP > overTOP > compositeTOP > feedbackTOP > levelTOP > blurTOP > transformTOP > noiseTOP > tileTOP > edgeTOP > noiseCHOP > mathCHOP > nullCHOP
   - constantTOP 1280x720 alpha 0 as canvas; circleTOP 256 px; overTOP: set Fixed Layer + Pre-fit Overlay = Native Resolution
   - noiseCHOP channels 'x y' (space-separated list), Time Slice on; math range -1..1 -> -0.6..0.6; null; drive over translate x/y
   - feedbackTOP: Target TOP = the comp output; feedback output wired back as 2nd comp input (loop: comp -> feedback -> comp; target is the end of the c...
   - Key: level opacity=0.9; scale per frame=1.01 / 0.99; noise range=-0.6..0.6; canvas=1280x720 | Trick: Draw by compositing a small generator onto a big canvas rather than moving the generator
2. **Audio Reactive Particles using TouchDesigner POPs** (elburz, 2026-10-19) `75525` video `4shfXcXvLDk` 1657s
   - Ops: pointgeneratorPOP > geometryCOMP > cameraCOMP > lightCOMP > renderTOP > nullTOP > transformTOP > linePOP > particlePOP > randomPOP > attributePOP > mathcombinePOP > trailPOP > rayPOP
   - Render rig: pointgeneratorPOP -> geometry COMP (draw points on, point size) + camera + light -> renderTOP -> nullTOP; transformTOP/black bg
   - Add particlePOP; make an 'end' (feedback target) inside it - ops between the two feedback nodes run every frame on the particles. Life expectancy +...
   - Set pointgenerator source to a small sphere; randomPOP (size 3, range -1..1) writes a direction vector to attribute N; map N to particlePOP Initial...
   - Key: particlePOP.Speed=raise for faster feedback; randomPOP size=3; age gravity scale=0.1; render format=32-bit float | Trick: particlePOP carries ID/age/velocity/lifespan/drag attrs automatically
3. **Rolling Tiles using POPs, CHOPs, and DATs** (vtln, 2026-10-20) `75531` video `dknjgwXUVBA` 1539s
   - Ops: containerCOMP > parameterCHOP > mathCHOP > nullCHOP > gridPOP > mergeCHOP > fieldPOP > patternCHOP > tableDAT > beatCHOP > noiseCHOP > chopexecuteDAT > constantCHOP > selectCHOP
   - containerCOMP sets res; parameterCHOP+math(divide)+null 'parent data' gives aspect ratio
   - gridPOP; parameterCHOP on it gives size/cols/rows; math chains compute cell size = size/(cols-1); merge -> null 'grid data'
   - fieldPOP mode Box; patternCHOP (ramp) gives column/row positions from -size/2..size/2, chop->table; field info shows bounds
   - Key: speed=0.005; noise offset=0.5; circle divisions=20; switch delay=1 ms (not 1 frame) | Trick: Export table DAT (path/parameter/enable/value) is a neat way to drive parameters from CHOP
4. **Driving Content with Parallel Timers in TouchDesigner -Tutorial** (elburz, 2022-05-03) `66155` video `6522QJIoW_Q` 1215s
   - Ops: moviefileinTOP > texture3dTOP > nullTOP > rectangleSOP > geometryCOMP > constantMAT > gridSOP > nullSOP > cameraCOMP > renderTOP > constantTOP > timerCHOP > tableDAT > selectCHOP
   - moviefileinTOP count.mov, play mode Locked to Timeline -> texture3dTOP cache size 100, prefill on -> null
   - rectangleSOP 1.77 wide in geometryCOMP; constantMAT color map = the 3D texture null
   - gridSOP 3.65x1.05, 2 rows x 3 cols -> null 'pos'; geometry instancing translate from pos P0/P1/P2; show point numbers to map instance index; camera...
   - Key: texture3D cache size=100; play mode=Locked to Timeline; timer mode=Parallel | Trick: Parallel Timers = many timers in one CHOP, indexed by row
5. **Easy GLSL Chromatic Aberration in TouchDesigner** (elburz, 2022-11-16) `66870` video `UoE1UOqFgLk` 1570s
   - Ops: moviefileinTOP > glslTOP > infoDAT
   - movieFileIn jellybeans.1.jpg -> glslTOP (check the auto-created info DAT for compile status)
   - Vectors page uniforms (prefix u): uInputRes = (me.inputs[0].width, me.inputs[0].height); uRedPos/uGreenPos/uBluePos (vec2, 0); uRedScale/uGreenScal...
   - GLSL: vec4 color = vec4(1.0); vec2 redPos = uRedPos/uInputRes; (same green/blue)
   - Key: extend mode=repeat/mirror; test image=1280x720 | Trick: Prefix uniform names with u to tell them from locals
6. **Using "run" To Delay Python Code** (Ivan, 2022-12-08) `66947` text post
   - Ops: textDAT
   - run('print("hi")', delayFrames=60); run(print, 'hello,', location, delayMilliSeconds=2000)
   - args: run('print(args[0])', value) - args evaluated when run() is called; names inside the script string evaluate at execution
   - run(..., endFrame=True) defers to end of current frame
   - Key:  | Trick: Pass a callable instead of a string - more readable and refactor-safe
7. **tdu.Dependency tutorial** (drum-computer, 2022-07-28) `66489` video `kEQAsx6Ar_8` 2608s
   - Ops: baseCOMP > textDAT > parameterexecuteDAT > textCOMP
   - Example: movie bin extension with read/clear buttons and a UI label 'N movies'
   - Push: extension writes directly to UI (couples code); Pull: UI polls (wasteful)
   - Dependency: self.movie_list = tdu.Dependency([]); read through .val in expressions/promoted properties; assign via .val = new
   - Key:  | Trick: Reassign .val or call modified() - mutating in place silently doesn't update
8. **Enhance your TD development by using python type hints** (drum-computer, 2022-12-05) `66956` video `uQoqs-KhIQg` 1256s
   - Ops: baseCOMP > textDAT
   - Extension DATs saved as .py in a folder, referenced in each COMP as mod.<file>.<Class>(me) and promoted
   - In extension: import td; self.ownerComp: td.baseCOMP = ownerComp
   - from playlist_extension import PlaylistExtension; self.playlistComp: PlaylistExtension = op('playlist')
   - Key:  | Trick: td module is closed - editor shows unresolved import but TD resolves it
9. **Instance and offset an animated FBX using GLSL** (Artechs, 2022-01-27) `65752` video `FjMQOa0Znmo` 2410s
   - Ops: fbxCOMP > alembicSOP > nullSOP > soptoCHOP > choptoTOP > texture3dTOP > lfoCHOP > chopexecuteDAT > textDAT > renderTOP > cameraCOMP > lightCOMP > geometryCOMP
   - Problem: each FBX copy is heavy (31k points); fps drops with 4 copies
   - Blender: import FBX, join meshes (Ctrl+J), set frame range (17 frames at 30fps), export Alembic
   - alembicSOP: time slider in frames (34 frames at 60 fps); soptoCHOP tx/ty/tz point positions (31000 samples) -> choptoTOP -> texture3dTOP stores one...
   - Key: cache size== number of animation frames; project.realTime=0 while recording | Trick: project.realTime = 0 puts TD in non-real-time so each frame is recorded
10. **Lego Brick Instancing** (mattrosslive, 2022-11-22) `66894` video `fu3Csj-NxyQ` 1588s
   - Ops: boxSOP > tubeSOP > mergeSOP > geometryCOMP > cameraCOMP > lightCOMP > renderTOP > phongMAT > transformTOP > nullTOP > gridSOP > soptoCHOP > mergeCHOP > nullCHOP
   - boxSOP base; tubeSOP stud; mergeSOP; tube center y = op(box).par.sizey/2 + me.par.height/2; radius = box.sizey/4; height = box.sizey/4 (parameter-l...
   - geo + phong MAT + camera + light -> render; transformTOP bg alpha 1 comp over black
   - gridSOP 20x20 -> soptoCHOP -> mergeCHOP (room for more data) -> null 'instance data'; geo Instance tab: translate from tx/ty; uniform scale down; f...
   - Key: grid=20x20 (cols = rows*2 for 16:9); fit filter=nearest; ramp interpolation=step | Trick: Link all brick dimensions by parameter references so the model rescales safely
11. **Holiday Point Cloud Transitions - Tutorial** (elburz, 2022-12-08) `66967` video `o0Hli7C1RME` 1087s
   - Ops: fileinSOP > transformSOP > sprinkleSOP > nullSOP > soptoCHOP > choptoTOP > nullTOP > sphereSOP > switchTOP > geometryCOMP > cameraCOMP > renderTOP > noiseTOP > levelTOP
   - fileinSOP (free OBJ from TurboSquid) -> transformSOP scale to match -> sprinkleSOP 10000 points -> null
   - soptoCHOP (attribute selection P) -> choptoTOP data format RGB, image layout Fit to Square -> null; repeat per model; all TOPs must be the same siz...
   - Transition shape: sphereSOP polygon radius 0.5 + sprinkle -> same chain
   - Key: points=10000; texture size=100x100; instance sphere radius=0.001-0.002; blend=switch blend between inputs | Trick: Position data as an RGB float texture = a point cloud you can blend with plain TOP ops
12. **Directional Motion Detection and Tracking using Webcam in TouchDesigne** (function.store, 2022-11-23) `66900` video `ju4F1cGhE6Q` 941s
   - Ops: ndiinTOP > videodeviceinTOP > opticalflowTOP (palette) > reorderTOP > thresholdTOP > analyzeTOP > toptoCHOP > mathCHOP > logicCHOP > mergeCHOP > speedCHOP > circleTOP > nullCHOP
   - Webcam (or NDI In) -> Optical Flow (Tools palette); R = x motion, G = y motion per pixel
   - reorderTOP: output red only (G,B -> zero)
   - two thresholdTOPs: less-or-equal 0 (one direction) and greater-or-equal 0 (the other)
   - Key: speed limits=-0.5..0.5 | Trick: Direction from sign of optical flow pixels, counted with Analyze Sum
13. **Automatic TOP Cropping in TouchDesigner - Tutorial** (elburz, 2022-04-28) `66132` video `zv1Q56E6ajI` 1984s
   - Ops: rectangleTOP > lfoCHOP > mathCHOP > nullCHOP > constantCHOP > cropTOP > toptoCHOP > shuffleCHOP > stretchCHOP > analyzeCHOP > logicCHOP > selectCHOP
   - rectangleTOP long/skinny + lfo->math (-1..1 -> 0..360) rotate; constantCHOP width/height = op('rectangle1').width/height
   - cropTOP: set units to Pixels (not fractions)
   - topToCHOP (alpha only): each row/column becomes channels/samples; shuffle (swap samples<->channels) to get a profile along x then y
   - Key: crop units=pixels | Trick: Visualise CHOP data against the TOP while building
14. **Banana from bananas (Dart-throwing) | Space filling algorythm** (igalabs, 2022-02-24) `65852` video `QIAzH5CsRgs` 1312s
   - Ops: constantTOP > circleTOP > fitTOP > transformTOP > feedbackTOP > compositeTOP > analyzeTOP > analyzeCHOP > toptoCHOP > noiseCHOP > mergeCHOP > renameCHOP > switchTOP > logicCHOP
   - constantTOP alpha 0 custom res = blank scene; circleTOP radius 0.5 -> fitTOP to the scene res -> transform1 (rotate/scale) -> transform2 (translate...
   - feedbackTOP holds scene; comp1 = Multiply(scene, object) to test overlap; comp2 = Over(scene, object) to add it
   - analyzeTOP/analyze maximum of alpha of comp1 -> TOP to CHOP: any overlap > 0
   - Key: noise type=random; rotation amplitude=180; start size=0.2 | Trick: Multiply composite = cheap collision test, analyze max = overlap flag
15. **Interactive Particles with Optical Flow and ParticlesGPU 2022** (elburz, 2022-11-07) `66824` video `xODS0pZ6CEo` 1276s
   - Ops: ndiinTOP > opticalflowTOP (palette) > particlesGpuCOMP (palette) > compositeTOP > nullTOP
   - Drag particlesGpu from palette (leaves default; 5 inputs = new version)
   - Palette Tools > Optical Flow, feed video into it, output to particlesGpu input 4
   - Forces tab: optical flow magnitude + input size remap; extend bounding box so flow volume covers the region
   - Key: min build=2022.28040; birth=20 | Trick: Optical flow is a 2D field applied as an extruded tube through the 3D volume
## Recurring techniques / ops in this slice

Most-used ops: renderTOP (30), nullTOP (30), geometryCOMP (30), cameraCOMP (28), mathCHOP (22), textDAT (19), compositeTOP (19), nullCHOP (16), noiseTOP (15), transformTOP (15), levelTOP (13), feedbackTOP (12), lightCOMP (11), noiseCHOP (10), rampTOP (10), mergeCHOP (10), moviefileinTOP (10), selectCHOP (10), containerCOMP (10), tableDAT (9), chopexecuteDAT (9), constantTOP (9), lfoCHOP (8), soptoCHOP (8), nullSOP (8), switchTOP (8), websocketDAT (8), buttonCOMP (8).

- Feedback loop mindset: every op on the feedback wire is recursive (level 0.9-0.95 trails, blur, transform scale 0.99/1.01, tile): JkKHKsY31no, pcI9PuU9O_c, vLV5e6OMhBI, 1-ocK5XcRt4-style art series.
- Instancing from data textures/CHOPs: gridSOP -> soptoCHOP -> geo instancing; textures as data (choptoTOP fit-to-square RGB 32-bit, 16-bit on Spout): fu3Csj, o0Hli7, W3HNjR, z2Jgp, p-lhm, FjMQO.
- Ortho camera width = op('render1').par.resolutionw for pixel-unit geometry art (Mohr, Vasarely, Ikeda, Whitney, Kandinsky) - the IIHQ artist series.
- Python extensions + global shortcut + Tweener/UI patterns: Amazing Robot UI Basics 1-3, QR photobooth, type hints, tdu.Dependency, run() delays (66947).
- WebSocket/OSC/NDI/serial bridges: websocketDAT + JSON series (6 parts + body tracking), oscout->Max, NDI tools, ndi-python, TDAbleton.
- Optical flow for interaction: directional webcam detection (ju4F1c), particlesGPU optical flow input (xODS0), SOP particle exercise (HX2WN).
- POPs (2025 era): particlePOP with feedback target loop, trailPOP, lookuptexturePOP, fieldPOP/gridPOP/limitPOP/quantizePOP - 3 posts from Oct 2026.
- CHOP-side tricks: Timer CHOP parallel mode, Math ranges, Lag for MIDI toggles, Logic/Analyze for pixel scans (auto-crop), Audio Play CHOP list playback.

## Top authors

elburz 45 (The Interactive & Immersive HQ); blankensmithing 10 (Torin Blankensmith); Unveil_studio 4 (Unveil); uisato 4 (uisato); amazingrobot 4 (Amazing Robot); drum-computer 3 (Denis Akopov); invisiblesignal 3 (Blake Marques Carrington); 3dwalker 3 (Hou2Touch | Stanislav Glazov); tekt 3 (tekt); Ivan 2.
`elburz` posts the Interactive & Immersive HQ videos (Elburz, Matthew Ragan, Jack DiLaura, Crystal Jow, Joel, Sal); blankensmithing = Torin Blankensmith (websocket series, body tracking, background removal, Shader Park); Unveil_studio, uisato, amazingrobot (UI Basics), tekt (RayTK), 3dwalker = Hou2Touch '10 Minutes' series.

## Newer-build / Windows-only / not-on-this-Mac flags

- `66469` Zed 2i 3D Scanning in TouchDesigner - Tutorial: NO - ZED SDK requires NVIDIA CUDA
- `66326` Elgato Stream Deck + TouchDesigner - Tutorial: API Ninja plugin Windows-only; other web request plugins work on Mac
- `66184` Generative Andy Warhol in TouchDesigner - Tutorial: Kinect Azure SDK is Windows-only; webcam path works on Mac
- `66288` Getting Started with TensorFlow-GPU and TouchDesigner: NO - Windows/NVIDIA only
- `66233` TDinstanceUE - Streaming TouchDesigner instancing data into : Spout is Windows-only; on Mac use Syphon (same texture-as-data idea) - Unreal on Mac via Syphon plugin
- `66373` Zed 2i First Look in TouchDesigner - Tutorial: NO - ZED SDK requires NVIDIA CUDA (Windows/Linux)
- `65975` Custom Depth Map from Kinect & RealSense Point Clouds in Tou: Kinect Azure SDK is Windows-only; technique applies to any point-cloud TOP
- `tutorial` Instrumentos Controlados por Movimiento – TouchDesigner, Abl: Kinect CHOP Windows-only
- `65957` Nvidia Flex Emitter and Collision Basics in TouchDesigner: NO - Nvidia Flex is Windows/NVIDIA only
- `65763` Nvidia Flex Basics in TouchDesigner: NO - Windows/NVIDIA only
- `mac` field: 'yes' = only core ops/Python, no Windows-only feature mentioned in the video (not tested by me); otherwise the limitation is named.
- Newer-than-the-video features now stable on 31550: Audio VST CHOP (experimental in 2021.38110: 8o6_v, HnAy3, sae-Vo), Vulkan backend (sae-Vo), Timecode class (9g9m1), tdu.Dependency callbacks 2022+ (kEQAs), particlesGPU optical-flow input needs 2022.28040+ (xODS0). None of the used op types is missing from 31550; Nvidia Flex ops exist as `nvidiaflexsolverCOMP` but are Windows/NVIDIA only (skipped in our dump).
- RayTK (EehwTr8F4Xs, P9NMD, Uo2wC, 66312/66229/65777 posts) is a third-party .tox toolkit, not a core op family; its Vulkan/Metal compatibility on Mac must be tested before relying on it.
- Paid/gated: Patreon components (blankensmithing body tracking + websocket tox, Unveil SD TOP, Function Store, uisato, Attraktors Designer); Gumroad Lego project. Only free derivative.ca attachments downloaded (small .toe/.zip/.tox, not opened): see files list in the jsonl; folders under `research_src/tutorials/files/<postid>/`.

## Notes for builders

- Ops not in INDEX_2025.31550 (dumped/skipped/failed lists): none after name checks; palette COMPs (particlesGpu, lister, opticalflow, chromaKey) are palette tox files, not op types.
- Tutorials recorded on Windows/NVIDIA often show features missing on this Mac (Kinect, ZED, Nvidia Background, Flex, Spout, NDI HX); Mac equivalents: Syphon, NDI, webcam, optical flow.
