# Tutorials slice 09 (derivative.ca listing pages 48-53), read 26 Oct 2026

Data: `research_src/tutorials/slice_09.jsonl` (95 unique tutorials; the six listing pages hold 120 slots, 25 were repeats
because the newest-first list shifted while crawling). Transcripts: `research_src/tutorials/transcripts/<ytid>.txt`.
Dates: 5 posts are Oct 2026 (Pao Olea, VTLN, Unveil, 3x Interactive & Immersive HQ); the other 90 are Apr-Oct 2020, so
most advice dates from builds 2020.20xxx-2020.26xxx. Ops were checked against `INDEX_2025.31550.json`, which omits device/IO
ops (oscin, midiin, audiodeviceout, keyboardin, videodevicein, spout, engine...), so "not in index" is not "not in build".

## Counts
- By category: workflow 17, 3D/render 16, GLSL 10, TOP 9, audio 9, Python 5, typography 5, SOP 5, COMP/UI 4, POP 3,
  output 3, ML/AI 2, mapping 2, CHOP 2, camera/interactive 2, other 1.
- Relevance (0-3): 3 = 31, 2 = 40, 1 = 23, 0 = 1 (networking talk).
- Videos: 79 YouTube (about 29 h total), 6 Vimeo, 10 posts with no video (written pages, paid course, playlists).
- Transcripts: 73 of 79 YouTube videos have a text file. 13 of those are weak: Korean (7 Caroline Reize videos, key steps
  translated from chapters + garbled captions), Japanese (TDSW GLSL ep.1, translated), Russian meetup (not analysed, 2.6 h),
  Spanish (day 7), music-only (SD TOP), mis-detected German/Dutch (Dith dsgn particles, noones_img time machine).
  Not obtained (no captions on the video or only applause): 63186, 62989, 62988, 62948, 62869, 62863.
- YouTube rate limit: HTTP 429 on caption requests hit twice (shared IP with the other agents); asking for the
  original-language track (`.*-orig`) first, one video at a time with 4 s gaps, fixed it. No cookies; nothing downloaded
  except captions + JSON metadata.
- Vimeo (6 posts): yt-dlp reached 3 (Darien Brito CA part 1, Hoepffner x2: title/duration only, no captions); 3 are login
  walled/404 (David Braun x2, petitsapin). No Vimeo captions retrieved.
- Free project files downloaded (never opened), `research_src/tutorials/files/<postid>/`: 62751 (1 toe), 62778 (4 tox),
  62817, 62828, 62863, 62910 (wavy_block_SOPs 840 KB), 62915, 63125 (toe each), plus GitHub raw toe for 62854 and 62870. About 1.4 MB.
  Skipped: 62871 zip (64.5 MB > 50 MB). Patreon/paid only (not fetched): Pao Olea, VTLN, threedashes, elekktronaut, Noto,
  Artechs, Unveil SD TOP, NODE Institute volumetrics course. Free GitHub trees (not cloned): exsstas/TD-tutorials
  (render buffers, perfect loop, voxels, distance), DBraun/TouchDesigner_Shared (compute particles, NodeRender),
  franklin113/Tutorial-Repo, guidoschmidt/Touchdesigner.GenerativeMeshes, jhoepffner/TDinitiation.

## Top 15 as rebuild recipes
1. **BPM detection from audio (62764, alphamoonbase)**: `audiofileinCHOP` > `audiospectrumCHOP` (find bass) > `audiofilterCHOP`
   band-pass cutoff 40-50 Hz, rolloff 24, resonance up > `mathCHOP` (combine channels) > `triggerCHOP` on the kick >
   `speedCHOP` (time since last kick, reset by trigger) > `delayCHOP` 1 frame > `recordCHOP` (mode add, record segment
   samples 0-3, trigger = single-frame pulse) > `analyzeCHOP` average > `expressionCHOP` `60/me.inputVal` (x4 for 4 beats).
2. **GPU particles, TOP feedback + GLSL TOP (63213, karpik)**: `noiseTOP` (monochrome off) > `nullTOP` position_out / color_out >
   `sphereSOP` r 0.01 12x12 in `geometryCOMP` with instancing (translate from position texture, colour from colour) >
   `gridSOP` floor 15x15 > `pbrMAT` (metallic 0.3, rough 0.4) + `environmentlightCOMP` (noise as env map) > `renderTOP`.
   `feedbackTOP` x2 hold position + velocity; `glslTOP` update: `vel += g*0.03`, g=(0,-1,0); if pos.y<0 flip vel.y; add
   interactive gravity + attractor. Free project: gum.co/agIxq.
3. **Curl-noise particles (62951, threedashes, build 2020.20020)**: render rig > `glslTOP` compute passes with `feedbackTOP`
   for position, velocity, life, orientation, scale, colour textures > `geometryCOMP` texture instancing. Curl = finite
   difference of 3D simplex noise: copy `snoise` from the GLSL TOP help (Write a GLSL TOP > Perlin and Simplex 3D) and
   call it three times. Gives fluid-like swirl far cheaper than a fluid sim.
4. **Audio-reactive sliced type (62992, threedashes, 2020.23680)**: `textTOP` 1080x1080 Arial Black 220 > `nullTOP` text;
   `constantCHOP` segments=2 gap=6 > `rectangleTOP` slices (custom resolution from constants) > `transformTOP` copies as
   mask; `displaceTOP` fed by `noiseTOP` (translate `absTime.seconds*0.1`); audio `analyzeCHOP` RMS power > `mathCHOP`
   boost > `limitCHOP`; `thresholdTOP`/trigger = snare, `countCHOP` swaps words. No GLSL.
5. **Stripe-style gradient waves (63028, threedashes, 2020.23680)**: `gridSOP` > `geometryCOMP` + `cameraCOMP` + `renderTOP`;
   `glslMAT` vertex displacement from noise; 3 copies of `noiseTOP` with different seeds as RGB; one `null` named time
   (`speedCHOP`/constant x0.05) so speed is global; grain + overlay in `compositeTOP`. Patreon for the toe.
6. **Rolling tiles with POPs (75531, VTLN, Oct 2026)**: `parameterCHOP` (parent width/height) > `mathCHOP` aspect >
   `gridPOP` > `parameterCHOP` + `mathCHOP` (cell size = size/(cols-1)) > `mergeCHOP` > null grid data; `fieldPOP` mode box,
   size 2x the grid so a full row/column is covered; `patternCHOP` ramp (length=cols, range -sizeX/2..sizeX/2) +
   `tableDAT` for positions; `beatCHOP` + `noiseCHOP` (offset 0.5, end mode samples=0) + `chopexecuteDAT` pick a random
   line, mode and direction; `evaluateDAT` table sets field size per mode; `limitPOP` snap. Part 2 (post/shapes) separate.
7. **Audio-reactive sparks with Particle POP (75525, Interactive & Immersive HQ, Oct 2026)**: `pointgeneratorPOP` >
   `geometryCOMP` + camera + light > `renderTOP` > null (draw points on, line geometry for streaks); `particlePOP`
   (own feedback; tick colour and line width in its attribute list); `randomPOP` upstream writes colour / line width per
   particle; gravity, trails, `rayPOP` + `noisePOP`; audio analysis drives emit/noise amplitude; post in TOPs.
8. **Perfect seamless loops (62961, exsstas)**: one master phase from `patternCHOP` ramp over the timeline length, every
   driver goes through `lookupCHOP` with a periodic curve (sine) so start = end; noise loops by moving along a circle in two
   coordinates, not a line; audio-reactive trick keeps it seamless. Toe on GitHub exsstas/TD-tutorials.
9. **Slit-scan with feedback (62945, elekktronaut)**: `videodeviceinTOP` > `fitTOP` > `cropTOP` strip > two `feedbackTOP`
   loops (one per side) each with `transformTOP` shift > `flipTOP` to un-mirror > extra FX. Use the stored webcam clip here.
10. **Stream TD to Instagram Live (62828, Jacob)**: `rampTOP` (animated phase, 720x1280) > `spoutoutTOP` (Windows; on macOS
    use Syphon Spout Out TOP) > OBS source `TSSyphonSpoutOut`, x264 ultrafast 3000 Kbps, canvas 720x1280, Area downscale >
    Yellow Duck logs in to IG and issues an RTMP URL + stream key (new each stream) pasted into OBS. Toe attached (3.66 KB).
11. **Projection mapping with CamSchnappr (63395, noones_img)**: Blender model, UV unwrap, FBX scale 0.001 (+ paper model) >
    `fbxCOMP` + camera + light + `renderTOP` + `phongMAT` (colour map = 9x9 `noiseTOP` > `fitTOP` 1024 nearest) >
    `windowCOMP` (borders off, screen number) > palette CamSchnappr on the render, add `soutSOP`, rotate X -90 > pick 5
    point pairs on model vs output.
12. **Movie preloading, no frame drops (63116, Elburz)**: `moviefileinTOP` viewer off; `preload()` the next clip about 1 s
    before it plays while the current one runs; check pre-read state before switching; `unload()` the old; recursive
    `run(..., delayFrames=1)` instead of `while`; keep a playlist script (63273 shows the while-loop replacement).
13. **Voxelise any geometry (62885, exsstas)**: point positions as texture, snap to a grid by rounding (`limitTOP`), instance
    boxes from the snapped texture (so cubes touch, unlike blended instances). Extensions: palette Point Cloud Transform,
    raymarching, Kinect point cloud, SOP scatter, noise subtraction, merged clouds. Toe on GitHub.
14. **Distance-based instancing (62930, exsstas)**: `objectCHOP` camera (or light) to instance positions (1000 samples) >
    `mathCHOP` range > scale / `lookupCHOP` colour (orange to dark blue, 32-bit float) / noise / texture choice, all
    without GLSL; swap the camera for a `lightCOMP`.
15. **Custom component with custom parameters (62946, elekktronaut)**: `baseCOMP` containing `inTOP` > grain `noiseTOP` stack
    > `outTOP`; Customize Component adds page "Controls" with toggle Power + floats; `parameterCHOP` inside targets the parent
    (custom on, built-in off); bind slider/button widgets. Runners-up: render buffers (63000/63019), linear vs gamma PBR
    (62871), point-cloud rotation in GLSL (62808), life-attribute driven instances (Particle SOP post), TDAbleton (63247).

## Recurring techniques and ops
- Every 3D build starts `geometryCOMP` (33), `renderTOP` (21), `cameraCOMP` (17), `lightCOMP` (11); data via `noiseTOP` (17),
  `mathCHOP` (12), `feedbackTOP` (12), `glslTOP` (11), `compositeTOP` (11), `rampTOP` (9), `nullTOP` (13).
- "Everything is data": SOP/CHOP/TOP converted to textures or channels, then GPU instancing (position texture or CHOP
  channels into the instance page). Seen in 63213, 62951, 62808, 62964, 62885, 62930, 63256, 62979.
- Time: drive with `absTime.seconds*k` or one shared null/Speed CHOP; loops need a single phase (62961).
- Always end a chain with a Null and reference the Null (63194); `lookupCHOP` curve + `mathCHOP` range remaps.
- GLSL: TOP feedback textures as particle state (63213, 62951, 63196), vertex-shader displacement (63028, 62948), render
  buffers via GLSL MAT (63019), 2D texture arrays + point sprites (62870), transforms in 10-20 lines (62808).
- Operations craft (Elburz): preload media, no `while` (use `run(delayFrames=1)`), web front-ends for control, Node-RED,
  TDAbleton, Tox Tools for collaboration, hot spare + task scheduler + process watcher for permanent installs, Engine COMP
  (separate process per heavy component), Op Find DAT for bulk edits (set all TOP formats to 32-bit float).
- Bass beat: band-pass 40-50 Hz + resonance (62764); Logic CHOP "on when value changed" turns Ableton beat index into pulses.
- POPs (Oct 2026): 3 new tutorials use Particle POP, Trail POP, Look Up Texture POP, Grid/Field/Limit POP; per-point
  attributes (colour, line width) written by Random/Noise POPs; keyboard hotkey wired to Trail reset.

## Top authors (posts in slice)
elburz / Interactive & Immersive HQ 22 (ops craft, sensor, Python, installs), Kohui / Noto The Talking Ball 7 (PBR,
instancing, free toe + Patreon), digital.rain (Caroline Reize, Korean beginner) 7, elekktronaut 6 (UI, TDAbleton, slitscan, Line
MAT), exsstas 6 (render buffers, loops, voxels, GLSL tricks; free on GitHub), threedashes 4, Javier Casadidio 4,
smooth_isfast (Hukir) 3, David Braun 3, Artechs / Factory Settings 2, TimFranklin 2.

## Flags
- Windows / NVIDIA only: NVIDIA Flow fire (62914) and Flex + Bullet (62817, 62863: `flexsolverCOMP`, `nvidiaflow*` are not
  in 31550); Spout out for Instagram stream (62828, use Syphon on macOS); Notch Blocks (63073); SD TOP StreamDiffusion (75505,
  paid; GPU requirements not confirmed, captions are music only); 63017 recommends Windows for installations (our host is macOS under Rosetta).
- Needs care on macOS Vulkan/Metal (untested): GLSL compute / atomic counters (63196), multi-buffer GLSL MAT (63019).
- Newer-build items are fine: POP ops, `timecodeCHOP`, Engine COMP all exist in 2025; 2020 builds predate POPs/Engine fixes
  (Engine COMP was "new and buggy" in 63059).
- Parameter names and defaults in 2020 videos may differ from 31550: verify each parameter with `td_get_pars` before use.

## Open questions
- Which 2020 tutorials still run unchanged on 31550 (GLSL TOP setup and parameter names are the likely breakages)?
- Hoepffner GLSL particles (62769) and Brito cellular automata (62778) look good but only Vimeo metadata was reachable.
- Toe/tox files were not inspected (TD binary); load them only in a scratch project when needed.
