# Tutorials slice 04 (derivative.ca listing pages 18-23), 26 Oct 2026

Source list: `derivative.ca/community?sort_by=created&type[]=23&page=18..23`. Data: `research_src/tutorials/slice_04.jsonl`
(95 rows), transcripts in `research_src/tutorials/transcripts/<ytid>.txt` (shared folder). Target build: TD 2025.31550 (macOS).
Posts are mostly Dec 2023 - Sep 2024 (TD 2023.1xxxx era, "made_with" = 2023.x is inferred from upload date); five
"featured" posts (Oct 2026, POP tutorials) sit in a sidebar on every listing page and are included once.
Each page = 15 own rows + 5 sidebar rows, so 6 pages = 90 + 5 = **95 unique tutorials** (not 120).

## Counts
- Tutorials read (post page fetched, parsed, analysed): **95**. YouTube only (no Vimeo). 35 h of video in total.
- Transcripts: **82 fetched** (YouTube auto-captions, en), **13 without a usable one**: 5 videos have no captions at all
  (audiodevout's silent/music-only Noise Sculpting series 4rm5dcoQHBc, Qrtwn5XjDzk, Mu1TpRVujuY, s8ea30HlTHE, kcZH2zcHANc) and
  8 were blocked by HTTP 429 on the caption endpoint (shared IP with the other 9 agents) after 4 retries: those rows are
  built from post text + description + chapters and say so in `teaches`. Two fetched transcripts are not narration (75505 SD TOP
  demo = song lyrics, 69639 grid patterns = music).
- Category counts: 3D/render 23, TOP 15, camera/interactive 14, audio 7, ML/AI 6, Python 6, workflow 5, GLSL 4, output 3, typography 3, mapping 3, POP 3, CHOP 2, COMP/UI 1 (no DAT-only, SOP-only, mapping-projection or output-to-Resolume tutorials in these pages beyond the 3 mapping/3 output rows)
- Mac: yes 78, no 12 (NVIDIA/Windows/Kinect plugins), unknown 5. Relevance 3: 29, 2: 46, 1: 17, 0: 3.
- Files: derivative.ca attachments only on 4 posts. Downloaded (not opened): `files/69296/interactive windows.toe` (955 KB) and
  `files/69328/Tut gaze.6.toe` (974 KB). Skipped: TDBOY emulator zip 45 MB and TDCUBE toxes (relevance 0, emulator/ROM rights). Most
  other "project files" are Patreon (paid or free-with-account): recorded only.

## Top 15 as rebuild recipes (ops in order; key values said aloud)
Op names are TD type names; all are in our 31550 index unless marked.

1. **75525 Audio Reactive Particles with POPs** (elburz/HQ, Oct 2026): `pointgeneratorPOP` (tiny sphere) -> `randomPOP` size 3 (-1..1) into `N` ->
   `attributePOP` Color -> `particlePOP` (its own feedback target: `inPOP`/`outPOP` pair; tick custom attributes in *Input Attributes*; map `N` ->
   initial velocity) -> inside loop `mathcombinePOP` (pre tab: age*0.1 = gravity, subtract from P.y) -> `trailPOP` (match by attribute = part ID) ->
   line MAT 2 px; `rayPOP` pushes points to a box surface. Audio: `audiofileinCHOP` -> mono -> `analyzeCHOP` RMS -> `lagCHOP`; Math 0..0.5 ->
   50..1000 integer = birth rate (raise max particles); snare -> `countCHOP` = noise seed / box scale. Post: `lookupTOP`+ramp, render 32-bit float,
   `bloomTOP`, arctan highlight roll-off + `hsvadjustTOP`, `lumablurTOP` masked by flipped soft circle.
2. **75531 Rolling Tiles with POPs/CHOPs/DATs** (vtln): `gridPOP` -> `feedbackPOP` -> `fieldPOP` (box) -> `transformPOP` (speed 0.005, direction from
   noise -> `expressionCHOP` -1/1) -> `limitPOP` (P.xy, loop, +/- grid/2 + half cell) -> `quantizePOP` to cell size (snap) -> `circlePOP`+`copyPOP`.
   Row/col positions: `patternCHOP` ramp (-size/2..size/2) -> `choptoDAT`; `beatCHOP`+`noiseCHOP`(1 sample)+`chopexecuteDAT` picks a random
   line; an *export table* DAT (path, parameter, enable, value) writes Field TX/TY and sizes; `switchPOP` index 1 then back to 0 after 1 ms.
3. **75535 Aura Flow** (pao.olea): `pointgeneratorPOP` torus (1000-5000 pts) -> `noisePOP` (translate absTime.seconds*0.1) -> `trailPOP` (points & prims,
   increment 0.5) with `keyboardinCHOP` reset; colour by `lookuptexturePOP`+ramp from a second `noisePOP` writing attribute `noiseColor` with
   combine = none; `twistPOP` x2 (taper) with LFO -> Math (-50..150) strength; PBR MAT + noise-TOP env map + 4 lights; blur->level->add glow,
   bloom, RGB delay (B2 G4 R6).
4. **69679 Flow-field particles with TOPs only** (dcheesman): `rampTOP` x2 -> `reorderTOP` (R=u,G=v,B=life) 512x512 32-bit = start positions ->
   `feedbackTOP` + `compositeTOP` add (the "brain") -> Null position -> `geometryCOMP` instancing (8-div circle r 0.001, ortho cam bottom-left).
   Velocity: `noiseTOP` (animated) -> `slopeTOP` (32-bit, G = vertical luminance, zero point 0) -> `remapTOP` with positions as input 2
   (samples flow at each particle) -> added in the loop. Life in blue, reset by threshold; Level opacity 0.995; keyboard reset.
5. **69757 GLSL particle simulation** (dcheesman): random 32-bit RGBA noise = (u,v,z,life) -> `feedbackTOP` -> `glslTOP` (input0 start,
   input1 feedback, extend mirror) updates position with flow field + curl noise + life remap -> Null -> back to feedback; instanced
   Box/circle with colour on instancing tab 2; uniforms declared on Vectors page; 1080x1920.
6. **69641 No-code fluid** (dcheesman): 5 circles from a 5x1 32-bit RG noise -> `opticalflowTOP` (palette) -> `blurTOP` -> `feedbackTOP`
   -> `displaceTOP` (vertical source green, midpoint 0, weight 0.001) displacing itself + add current flow; effect loop: noise*input ->
   feedback -> displace by flow (0.001) -> over; Level opacity fades; mouse/multitouch via `multitouchinDAT`. Reset key on both loops.
7. **69971 Liquid feedback with the Bloom TOP**: `noiseTOP` (32-bit, colour, tz=absTime.seconds*0.1) -> `levelTOP` 0.6 -> `limitTOP` (floor, step 0.3,
   position ceiling) -> `bloomTOP` (pre black 0.45, pre gamma 0.5, radius 0.05, threshold 0.05, intensity 3.75, bloom only) = "null input";
   `feedbackTOP` -> `edgeTOP` -> `displaceTOP` (weight 0.001, repeat) driven by a 2nd Bloom of the feedback (pre gamma 1.5, threshold 0.5, fill 0.6);
   input `levelTOP` opacity 0.01 over the loop via `compositeTOP` (swap inputs), target = composite; `keyboardinCHOP` reset.
8. **69907 Audio-reactive voxel ripples** (dcheesman): audio -> `analyzeCHOP` RMS / `envelopeCHOP` -> `filterCHOP` -> circle scale -> optical
   flow feedback (displace weight about -0.002) = ripple height; `glslTOP` `vec4(vUV.st,0,1)` grid + ripple in B via `reorderTOP` (alpha = circle
   crop) = position; Box SOP 0.02 instanced, Phong MAT with shadows, 1280x1280.
9. **70171 Video-motion particles** (dcheesman): `resolutionTOP` quarter -> GLSL grid start positions; life = noise + feedback + add 1/100 per frame;
   `opticalflowTOP` of video -> `remapTOP` -> velocity feedback with *0.98 damping, 32-bit RGBA; position += velocity; reset on life >= 1.
10. **69723 Chromatic aberration**: 3x `reorderTOP` (R,G,B mono 32-bit) -> radial `rampTOP` (ease, flat centre, 32-bit) -> `slopeTOP` (32-bit RG, zero
    point 0) -> `displaceTOP` on R (+) and B (-) by slope*strength, G untouched; recombine.
11. **69616 Reaction diffusion in 3 minutes**: `noiseTOP` seed -> `feedbackTOP` -> sharpen (1) -> `blurTOP` (extend repeat) -> `crossTOP` with the seed ->
    back to feedback; blur amount = line size; swap for `lumablurTOP` driven by a 2nd noise for varied widths; `transformTOP` for zoom.
12. **69496 Light painting with Trace SOP** (HQ): video -> `chromakeyTOP` (value 0.99) -> `traceSOP` -> `deleteSOP` (keep last point via `infoCHOP` count-1)
    -> `soptoCHOP` -> `filterCHOP` -> `trailCHOP` (2 s) -> `choptoSOP`; `particleSOP` + `sortSOP` random on the line; 2 renders, bloom/radial blur,
    feedback Level 0.975 with 32-bit float RGBA.
13. **70269 LED sculpture content pipeline** (Ben Guerrette/HQ): draw animation as a tall image in Figma, one column per LED strip; `transformTOP` y driven by
    `lfoCHOP`; `cropTOP` per column (1 px high) -> `fitTOP` side by side -> `compositeTOP` -> sample RGB for LEDs. Easing in the drawn curves; audio
    waveform screenshots + measure grid for sync. (Directly reusable for PF26 LED pixel work.)
14. **69617 Pixel mapping to DMX**: SOP of LED positions -> `soptoCHOP` -> `choptoTOP` (50x1 UV map, RG) -> `remapTOP` (content, UV) -> `toptoCHOP` -> `shuffleCHOP`
    (interleave RGBRGB..) -> `dmxoutCHOP`; instancing preview from the same UV channels.
15. **69687 Time Grids** (elekktronaut): custom par Grid Size; `texture3dTOP` as 2D texture array, cache = grid^2; `timerCHOP` fraction -> Math (0..n-1) ->
    *replace index* + pulse each frame; `gridSOP` instancing of planes sampling slice index; ortho cam 1280x1280; turn Realtime OFF while recording.

## Recurring techniques/ops
- Feedback loops with a `keyboardinCHOP` reset and a fade (Level opacity 0.97-0.999, or black level) appear in 23 tutorials; **32-bit float** on every
  position/velocity/feedback chain is stated over and over.
- **Position/velocity as textures** (TOP-based particles): UV ramp or GLSL grid -> feedback -> remap/slope/optical flow -> instancing.
  Counts: `renderTOP` 47, `geometryCOMP` (instancing) 44, `noiseTOP` 38, `mathCHOP` 29, `levelTOP` 26, `rampTOP` 24, `feedbackTOP` 23.
- `opticalflowTOP` fed back into `displaceTOP` (weights 0.001-0.03, midpoint 0) = cheap fluid/ripples (Dean Cheesman x4).
- `slopeTOP` (32-bit, zero point 0) as a gradient/force field: chromatic aberration, flow fields, slope displacement.
- Instancing sources must have equal sample counts; texture-array (`texture3dTOP`) instancing for per-instance images.
- Audio: `analyzeCHOP` RMS / envelope, snare detection component, trigger+count for seeds; beat-counting to switch geometry.
- POP family (Oct 2026): `particlePOP` as its own feedback system, `attributePOP`/`randomPOP` for per-point data, `trailPOP` by part ID,
  `mathcombinePOP` for arithmetic on attributes, `limitPOP` loop + `quantizePOP` snap, `lookuptexturePOP` colour.
- Python: Timecode class (hours/minutes/seconds/frames), Logger COMP, ui.colors dictionary, TDFunctions presets, module DATs, export-table DAT pattern.
- Presenter tips worth keeping: set resolution explicitly on every generator (or tie to parent via Python); `me.par`/`parent().par` custom pars;
  turn viewers off to save GPU; `Realtime` off for frame-accurate recording; Independent Time COMP + Chop Execute to step slow AI nodes.

## Top authors
elburz/HQ (Interactive & Immersive HQ, 27 posts: Jack DiLaura, Crystal Jow, Marco, Joel, Sal), dcheesman (Dean Cheesman, 17, TOP/GLSL particle systems,
Patreon files), Unveil_studio (7, Python/GLSL, Patreon), elekktronaut (6, face tracking, instancing; free designer.tox on Patreon),
tekt (6, RayTK series), audiodevout (6, noise sculpting, silent), pao.olea (6, materials/POPs), blankensmithing/Torin (4, MediaPipe,
Shader Park, Teachable Machine, ElevenLabs plugins), ETCH-01 (4, Farsi/English beginner series), MechBullRodeo (3, "In Just 10 Nodes").

## Newer-build / platform flags
- Newer than most posts, relevant to our build: POP tutorials (75525, 75531, 75535) use 2025.3x POP operators: all present in INDEX
  (`particlePOP`, `trailPOP`, `rayPOP`, `fieldPOP`, `limitPOP`, `quantizePOP`, `mathcombinePOP`, `lookuptexturePOP`, `twistPOP`...).
  `bloomTOP` (2023.10000), `timecodeCHOP` + Timecode class (2023.11290), Logger COMP (2023.11000), Geo Text COMP (`geotextCOMP`) are in 31550.
- Not in our index / not operators: Mediapipe, Shader Park, StreamDiffusionTD, TouchDiffusion, SD TOP (Unveil, native; unverified here), TDBitwig,
  Teachable Machine, Whisper/ChatGPT/ElevenLabs plugins (third-party); Sharpen, Radial Blur, RGB Delay, Kaleidoscope, particlesGpu (palette).
- **Windows/NVIDIA-only or hardware (not usable on our Mac)**: `bodytrackCHOP`, `facetrackCHOP`, Kinect v2/Azure, ZED, StreamDiffusionTD /
  TouchDiffusion (CUDA), TDOmni (RTX Omniverse). 12 rows have `mac: no`. Mac alternatives: MediaPipe plugin (CPU), optical flow, blob track.
- Mac note from Dean: Macs have no multitouch; tick "Include Mouse" on Multi Touch In DAT.

## Open questions
- 69296/69328 `.toe` files are not unpacked (no loading); their op lists could be read with `toeexpand` if the user wants.
- The 8 rows built without transcript (69035 Bloom quick start, 69168 body-tracking orb, 69296 interactive windows, 69624 trace/blob tracking, 69740 slope displacement, 69771 audio kaleidoscope, 69813 instancing textures, 69946 particle text/Geo Text) can be upgraded by re-running yt-dlp for ids yNUPVy3eDn0, swQUS2Dr2q8, lOGqpaZCJNk, ioSVh06MySc, RJkQTBEkMYo, BiamWUjnBoY, bta99-w21wg, LcFg59oQHDs once the caption endpoint stops returning 429 (blocked about 50 min while 10 agents shared one IP).
